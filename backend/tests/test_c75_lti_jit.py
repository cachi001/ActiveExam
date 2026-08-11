"""C-75 sección 5: JIT provisioning + emisión de sesión + mapeo context_id→comision_id.

DB real (regla dura #4). Se reusan helpers de firma RSA del patrón de test_c75_lti_launch.

Cubre:
  5.1  Primer launch de un sub nuevo crea usuario con roles=["alumno"],
       auth_provider="lti", debe_cambiar_password=True, datos SOLO del id_token.
  5.2  Segundo launch del mismo sub NO duplica cuenta (idempotente).
  5.3  JIT ignora datos de identidad que no vengan del id_token validado
       (datos del token prevalecen siempre — no hay inyección vía fuente externa).
  5.5  Tras JIT/login exitoso se emite JWT de sesión propio (mismo emisor que /auth/login).
  5.6  Implementación: se verifica que el endpoint /lti/launch redirige al frontend
       con access_token y refresh_token tras un launch válido.
  5.7  context_id con mapeo configurado matricula al alumno en la comisión mapeada.
  5.8  context_id sin mapeo crea/loguea igual pero sin matricular.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.lti.launch_validation import CLAIM_DEPLOYMENT_ID
from app.application.lti.jit_provisioning import provisionar_o_recuperar_usuario
from app.infrastructure.auth.own_issuer import emitir_jwt_propio
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.lti import (
    LtiDeploymentConfiableModel,
    LtiNonceModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.presentation.api.v1.lti import create_lti_router

# ---------------------------------------------------------------------------
# Constantes de prueba
# ---------------------------------------------------------------------------

_ISS = "https://campustest.frm.utn.edu.ar"
_DEPLOYMENT_ID = "7:zztest"
_CLIENT_ID = "CLIENT_JIT"
_KID = "k-jit-1"

# ---------------------------------------------------------------------------
# Helpers criptográficos (mismo patrón que test_c75_lti_launch)
# ---------------------------------------------------------------------------


def _par_rsa():
    """Devuelve (pem_privada, jwk_publica con kid _KID)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = _KID
    return pem, jwk


def _claims(*, nonce, sub="mdl-99", name="Alumno LTI", email="alumno.lti@demo.test",
             context_id: str | None = None, aud=_CLIENT_ID, exp_delta=300):
    ahora = int(time.time())
    c = {
        "iss": _ISS,
        "aud": aud,
        "sub": sub,
        "iat": ahora,
        "exp": ahora + exp_delta,
        "nonce": nonce,
        "name": name,
        "email": email,
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }
    if context_id is not None:
        c["https://purl.imsglobal.org/spec/lti/claim/context"] = {
            "id": context_id,
            "label": "Curso de prueba",
        }
    return c


def _firmar(pem, claims):
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": _KID})


def _fetcher(jwk):
    """jwks_fetcher que devuelve el JWK de prueba sin HTTP."""
    return lambda _uri: {"keys": [jwk]}


# ---------------------------------------------------------------------------
# Fixtures de DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — test de integración omitido")
    return url


@pytest.fixture(scope="module")
def engine(db_url):
    eng = create_async_engine(db_url, poolclass=NullPool, future=True)
    yield eng


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def _limpiar_db(session_factory) -> None:
    """Limpia las tablas relevantes para aislar los tests."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text(
            "DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"
        ))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.execute(text("DELETE FROM lti_tool_key"))
        await s.commit()


async def _insertar_deployment(
    session_factory, *, comision_id: str | None = None, context_id: str | None = None
) -> LtiDeploymentConfiableModel:
    async with session_factory() as s:
        dep = LtiDeploymentConfiableModel(
            iss=_ISS,
            deployment_id=_DEPLOYMENT_ID,
            client_id=_CLIENT_ID,
            jwks_uri=f"{_ISS}/mod/lti/certs.php",
            comision_id=comision_id,
            context_id=context_id,
        )
        s.add(dep)
        await s.commit()
        await s.refresh(dep)
        return dep


async def _insertar_nonce(session_factory, *, nonce: str, state: str) -> None:
    async with session_factory() as s:
        s.add(LtiNonceModel(
            nonce=nonce,
            state=state,
            iss=_ISS,
            expira_en=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        await s.commit()


async def _usuario_por_id_institucional(session_factory, id_inst: str) -> UsuarioModel | None:
    async with session_factory() as s:
        return (
            await s.execute(
                select(UsuarioModel).where(
                    UsuarioModel.id_institucional == id_inst
                )
            )
        ).scalar_one_or_none()


async def _inscripciones_de(session_factory, usuario_id: str) -> list[InscripcionModel]:
    async with session_factory() as s:
        return (
            await s.execute(
                select(InscripcionModel).where(
                    InscripcionModel.usuario_id == usuario_id
                )
            )
        ).scalars().all()


# ---------------------------------------------------------------------------
# 5.1 / 5.2 / 5.3 — Servicio provisionar_o_recuperar_usuario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_primer_launch_crea_usuario_alumno(session_factory):
    """5.1: primer launch de un sub nuevo crea usuario con atributos correctos."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()

    dep = await _insertar_deployment(session_factory)
    claims = {
        "sub": "mdl-100",
        "iss": _ISS,
        "name": "Alumno Nuevo",
        "email": "nuevo@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        usuario, creado = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado is True
    # Rol canónico "estudiante" — la spec usa "alumno" informalmente, el enum es "estudiante".
    assert usuario.roles == ["estudiante"]
    assert usuario.auth_provider == "lti"
    assert usuario.debe_cambiar_password is True
    assert usuario.id_institucional == f"lti:{_DEPLOYMENT_ID}:mdl-100"
    assert usuario.nombre == "Alumno Nuevo"
    assert usuario.email == "nuevo@demo.test"
    # password_hash es random — NO es None (no puede loguearse con password vacío)
    assert usuario.password_hash is not None


@pytest.mark.asyncio
async def test_jit_segundo_launch_no_duplica_cuenta(session_factory):
    """5.2: segundo launch del mismo sub reutiliza la cuenta existente."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()

    dep = await _insertar_deployment(session_factory)
    claims = {
        "sub": "mdl-200",
        "iss": _ISS,
        "name": "Alumno Existente",
        "email": "existente@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        u1, creado1 = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    async with session_factory() as s:
        u2, creado2 = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado1 is True
    assert creado2 is False
    assert u1.id_institucional == u2.id_institucional
    # Verificar que no hay dos filas en DB
    usuario_db = await _usuario_por_id_institucional(
        session_factory, f"lti:{_DEPLOYMENT_ID}:mdl-200"
    )
    assert usuario_db is not None


@pytest.mark.asyncio
async def test_jit_ignora_datos_fuera_del_id_token(session_factory):
    """5.3: el JIT usa EXCLUSIVAMENTE los claims del id_token validado.

    Verifica que nombre/email se toman del token — no existe otra fuente de
    entrada que el servicio acepte (la firma de la función no tiene parámetros
    extra de identidad que un atacante pueda inyectar).
    """
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()

    dep = await _insertar_deployment(session_factory)

    # Claims oficiales del id_token
    claims_validos = {
        "sub": "mdl-300",
        "iss": _ISS,
        "name": "Alumno Real",
        "email": "real@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        usuario, _ = await provisionar_o_recuperar_usuario(
            s, claims=claims_validos, deployment=dep
        )
        await s.commit()

    # Los datos vienen de claims_validos (id_token), no de ninguna fuente externa.
    # La función no acepta parámetros adicionales de identidad (diseño anti-inyección).
    assert usuario.nombre == "Alumno Real"
    assert usuario.email == "real@demo.test"
    assert usuario.id_institucional == f"lti:{_DEPLOYMENT_ID}:mdl-300"


# ---------------------------------------------------------------------------
# 5.5 — JWT de sesión emitido con mismo emisor que /auth/login
# ---------------------------------------------------------------------------


def test_jit_emite_jwt_sesion_mismo_emisor():
    """5.5: tras JIT, emitir_jwt_propio produce JWT con mismo emisor que /auth/login.

    Test PURO (sin DB): crea un UsuarioModel en memoria representando a un
    alumno LTI y verifica que emitir_jwt_propio produce un JWT correcto.
    La función emitir_jwt_propio es la MISMA que usa POST /auth/login — no hay
    una función paralela: ese es el contrato de la sección 5.
    """
    usuario = UsuarioModel()
    usuario.id = "00000000-0000-0000-0000-000000000001"
    usuario.id_institucional = "lti:7:mdl-500"
    usuario.email = "jwt@demo.test"
    usuario.roles = ["estudiante"]
    usuario.auth_provider = "lti"
    usuario.debe_cambiar_password = True

    _secret = "secreto-de-test-suficientemente-largo-32b"
    _issuer = "activeexam-auth"
    _audience = "activeexam"

    token = emitir_jwt_propio(
        usuario,
        secret=_secret,
        issuer=_issuer,
        audience=_audience,
    )

    decoded = jwt.decode(
        token,
        _secret,
        algorithms=["HS256"],
        audience=_audience,
        options={"require": ["sub", "iss", "aud", "exp", "iat"]},
    )
    # Mismo emisor que /auth/login (JWT_OWN_ISSUER = "activeexam-auth")
    assert decoded["iss"] == _issuer
    assert decoded["sub"] == str(usuario.id)
    # Rol canónico "estudiante"
    assert "estudiante" in decoded["realm_access"]["roles"]
    assert "exp" in decoded


# ---------------------------------------------------------------------------
# 5.6 — Endpoint /lti/launch redirige al frontend con tokens tras launch válido
# ---------------------------------------------------------------------------


def test_launch_endpoint_redirige_con_tokens(session_factory):
    """5.6: POST /lti/launch → 302 al frontend con access_token y refresh_token.

    Usa asyncio.run() en fixture sync (session_factory es module-scope sync en
    este módulo) para el setup de DB, luego TestClient para el request HTTP.
    """
    import asyncio as _asyncio

    async def _setup():
        async with session_factory() as s:
            await s.execute(text("DELETE FROM inscripcion"))
            await s.execute(text("DELETE FROM lti_nonce"))
            await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
            await s.execute(text("DELETE FROM lti_deployment_confiable"))
            await s.execute(text("DELETE FROM lti_tool_key"))
            await s.commit()

        dep = LtiDeploymentConfiableModel(
            iss=_ISS,
            deployment_id=_DEPLOYMENT_ID,
            client_id=_CLIENT_ID,
            jwks_uri=f"{_ISS}/mod/lti/certs.php",
        )
        async with session_factory() as s:
            s.add(dep)
            await s.commit()

        nonce = secrets.token_urlsafe(16)
        state = secrets.token_urlsafe(16)
        async with session_factory() as s:
            s.add(LtiNonceModel(
                nonce=nonce,
                state=state,
                iss=_ISS,
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=5),
            ))
            await s.commit()
        return nonce, state

    nonce, state = _asyncio.run(_setup())

    pem, jwk = _par_rsa()
    token = _firmar(pem, _claims(nonce=nonce))

    cipher = SecretCipher(key=Fernet.generate_key().decode())
    jwt_secret = "test-jwt-secret-suficientemente-largo"

    app = FastAPI()
    app.include_router(
        create_lti_router(
            session_factory=session_factory,
            cipher=cipher,
            jwt_secret=jwt_secret,
            jwt_issuer="activeexam-auth",
            jwt_audience="activeexam",
            frontend_url="https://frontend.test",
            jwks_fetcher_override=_fetcher(jwk),
        ),
        prefix="/api/v1/lti",
    )

    client = TestClient(app, follow_redirects=False)
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": token, "state": state},
    )

    assert r.status_code == 302
    location = r.headers["location"]
    assert "access_token=" in location
    assert "refresh_token=" in location


# ---------------------------------------------------------------------------
# 5.7 / 5.8 — Mapeo context_id → comision_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_context_id_mapeado_matricula_en_comision(session_factory):
    """5.7: context_id con mapeo configurado matricula al alumno en la comisión."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()

        # Necesitamos una comisión real — buscamos cualquiera existente en la DB de test
        comision_row = (
            await s.execute(text("SELECT id FROM comision LIMIT 1"))
        ).first()

    if comision_row is None:
        pytest.skip("No hay comisiones en la DB de test — salteo test de mapeo")

    comision_id = str(comision_row[0])

    dep = await _insertar_deployment(
        session_factory,
        comision_id=comision_id,
        context_id="ctx-prueba-001",
    )

    claims = {
        "sub": "mdl-700",
        "iss": _ISS,
        "name": "Alumno Mapeado",
        "email": "mapeado@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        "https://purl.imsglobal.org/spec/lti/claim/context": {
            "id": "ctx-prueba-001",
        },
    }

    async with session_factory() as s:
        usuario, creado = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    inscripciones = await _inscripciones_de(session_factory, usuario.id)
    assert len(inscripciones) == 1
    assert inscripciones[0].comision_id == comision_id


@pytest.mark.asyncio
async def test_jit_context_id_sin_mapeo_no_matricula(session_factory):
    """5.8: context_id sin mapeo → crea/loguea igual pero sin matricular."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE id_institucional LIKE 'lti:%'"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()

    # Deployment sin comision_id (no hay mapeo)
    dep = await _insertar_deployment(session_factory, comision_id=None)

    claims = {
        "sub": "mdl-800",
        "iss": _ISS,
        "name": "Alumno Sin Mapeo",
        "email": "sinmapeo@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        usuario, creado = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado is True
    inscripciones = await _inscripciones_de(session_factory, usuario.id)
    assert len(inscripciones) == 0
