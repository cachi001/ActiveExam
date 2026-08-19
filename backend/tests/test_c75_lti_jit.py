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

import asyncio
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

from app.application.lti.launch_validation import (
    CLAIM_DEPLOYMENT_ID,
    CLAIM_ROLES,
    LaunchInvalidoError,
)
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
_DEPLOYMENT_ID_2 = "8:zztest"  # segundo "Moodle" para los tests de colision de email
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
            "DELETE FROM usuario WHERE username LIKE 'lti:%'"
        ))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.execute(text("DELETE FROM lti_tool_key"))
        await s.commit()


async def _insertar_deployment(
    session_factory, *, comision_id: str | None = None, context_id: str | None = None,
    deployment_id: str = _DEPLOYMENT_ID,
) -> LtiDeploymentConfiableModel:
    async with session_factory() as s:
        dep = LtiDeploymentConfiableModel(
            iss=_ISS,
            deployment_id=deployment_id,
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


async def _usuario_por_username(session_factory, id_inst: str) -> UsuarioModel | None:
    async with session_factory() as s:
        return (
            await s.execute(
                select(UsuarioModel).where(
                    UsuarioModel.username == id_inst
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
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
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
    assert usuario.username == f"lti:{_DEPLOYMENT_ID}:mdl-100"
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
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
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
    assert u1.username == u2.username
    # Verificar que no hay dos filas en DB
    usuario_db = await _usuario_por_username(
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
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
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
    assert usuario.username == f"lti:{_DEPLOYMENT_ID}:mdl-300"


# ---------------------------------------------------------------------------
# 2.1/2.2 — colision de email (fix 2026-08-19)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_email_colisiona_con_cuenta_lti_de_otro_deployment_fusiona(session_factory):
    """2.1 (caso legitimo): el MISMO alumno real entra desde DOS Moodles
    distintos (deployments distintos) pero comparte el email real. La segunda
    identidad LTI se fusiona con la primera cuenta LTI en vez de duplicarla."""
    await _limpiar_db(session_factory)

    dep1 = await _insertar_deployment(session_factory, deployment_id=_DEPLOYMENT_ID)
    dep2 = await _insertar_deployment(session_factory, deployment_id=_DEPLOYMENT_ID_2)

    claims1 = {
        "sub": "mdl-400",
        "iss": _ISS,
        "name": "Alumno Multi Moodle",
        "email": "multi@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }
    claims2 = {
        "sub": "mdl-401",  # sub distinto: otro Moodle, mismo alumno real
        "iss": _ISS,
        "name": "Alumno Multi Moodle",
        "email": "multi@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID_2,
    }

    async with session_factory() as s:
        u1, creado1 = await provisionar_o_recuperar_usuario(s, claims=claims1, deployment=dep1)
        await s.commit()
    async with session_factory() as s:
        u2, creado2 = await provisionar_o_recuperar_usuario(s, claims=claims2, deployment=dep2)
        await s.commit()

    assert creado1 is True
    assert creado2 is False  # fusionado, no duplicado
    assert u1.id == u2.id
    assert u2.username == f"lti:{_DEPLOYMENT_ID}:mdl-400"  # sigue siendo la 1ra identidad


@pytest.mark.asyncio
async def test_jit_email_colisiona_con_cuenta_no_lti_rechaza_launch(session_factory):
    """2.1 (fix): si el email del launch ya pertenece a una cuenta que NO es
    LTI (login propio: tutor/docente/admin/alumno manual), el launch se
    rechaza en vez de devolverle a un tercero la cuenta/roles de otra persona.
    Bug real: un tutor cuyo email de Moodle coincidia con su email de
    plataforma terminaba "siendo" su propia cuenta de tutor al entrar por LTI."""
    await _limpiar_db(session_factory)
    dep = await _insertar_deployment(session_factory)

    async with session_factory() as s:
        await s.execute(text("DELETE FROM usuario WHERE username = 'tutor_colision_test'"))
        await s.commit()

    async with session_factory() as s:
        tutor = UsuarioModel(
            username="tutor_colision_test",
            email="tutor.colision@demo.test",
            roles=["tutor"],
            auth_provider="jwt",
            password_hash="hash-no-relevante",
        )
        s.add(tutor)
        await s.commit()

    claims = {
        "sub": "mdl-500",
        "iss": _ISS,
        "name": "Impostor Desde Moodle",
        "email": "tutor.colision@demo.test",  # mismo email que la cuenta tutor
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc_info:
            await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.rollback()

    assert exc_info.value.codigo == "email_en_uso_no_lti"

    # La cuenta tutor no debe haber sido tocada (ni matriculada, ni alterada).
    async with session_factory() as s:
        tutor_db = (
            await s.execute(select(UsuarioModel).where(UsuarioModel.username == "tutor_colision_test"))
        ).scalar_one()
        assert tutor_db.roles == ["tutor"]
        assert tutor_db.auth_provider == "jwt"
    inscripciones = await _inscripciones_de(session_factory, tutor_db.id)
    assert inscripciones == []

    # Tampoco debe haber quedado creada una fila "lti:..." huerfana para mdl-500.
    huerfano = await _usuario_por_username(session_factory, f"lti:{_DEPLOYMENT_ID}:mdl-500")
    assert huerfano is None


@pytest.mark.asyncio
async def test_jit_email_vacio_no_colisiona_entre_alumnos_distintos(session_factory):
    """2.2 (fix): si Moodle no comparte el claim `email`, dos alumnos reales
    DISTINTOS sin email no deben terminar fusionados en la misma cuenta por
    compartir el email vacio `""`."""
    await _limpiar_db(session_factory)
    dep = await _insertar_deployment(session_factory)

    claims_a = {
        "sub": "mdl-600",
        "iss": _ISS,
        "name": "Alumno Sin Email A",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        # sin "email"
    }
    claims_b = {
        "sub": "mdl-601",
        "iss": _ISS,
        "name": "Alumno Sin Email B",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        # sin "email"
    }

    async with session_factory() as s:
        ua, creado_a = await provisionar_o_recuperar_usuario(s, claims=claims_a, deployment=dep)
        await s.commit()
    async with session_factory() as s:
        ub, creado_b = await provisionar_o_recuperar_usuario(s, claims=claims_b, deployment=dep)
        await s.commit()

    assert creado_a is True
    assert creado_b is True
    assert ua.id != ub.id  # NO fusionados
    assert ua.email != ub.email
    assert ua.email != ""
    assert ub.email != ""


# ---------------------------------------------------------------------------
# Rol de staff en el claim `roles` (fix 2026-08-19)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_rol_instructor_sin_alumno_rechaza_launch(session_factory):
    """Fix real: un admin/docente de Moodle que clickea el link LTI de
    "Rendir examen" no debe terminar con una cuenta ActiveExam de alumno.
    Bug real: el dueño del proyecto entro con su cuenta ADMIN y se
    auto-provisiono como estudiante porque el claim `roles` se ignoraba."""
    await _limpiar_db(session_factory)
    dep = await _insertar_deployment(session_factory)

    claims = {
        "sub": "mdl-700",
        "iss": _ISS,
        "name": "Admin Que Preview",
        "email": "admin.preview@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        CLAIM_ROLES: [
            "http://purl.imsglobal.org/vocab/lis/v2/system/person#Administrator",
        ],
    }

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc_info:
            await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.rollback()

    assert exc_info.value.codigo == "rol_no_estudiante"
    huerfano = await _usuario_por_username(session_factory, f"lti:{_DEPLOYMENT_ID}:mdl-700")
    assert huerfano is None


@pytest.mark.asyncio
async def test_jit_rol_learner_crea_cuenta_normalmente(session_factory):
    """Regresion: un launch con rol Learner explicito sigue creando la cuenta
    de alumno sin problema (el chequeo de staff no bloquea al caso normal)."""
    await _limpiar_db(session_factory)
    dep = await _insertar_deployment(session_factory)

    claims = {
        "sub": "mdl-701",
        "iss": _ISS,
        "name": "Alumno Con Rol Explicito",
        "email": "alumno.rol@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        CLAIM_ROLES: [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
        ],
    }

    async with session_factory() as s:
        usuario, creado = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado is True
    assert usuario.roles == ["estudiante"]


@pytest.mark.asyncio
async def test_jit_rol_ausente_no_bloquea(session_factory):
    """Sin claim `roles` (algunas configuraciones de Moodle no lo mandan), el
    launch sigue funcionando -- no hay señal para bloquear."""
    await _limpiar_db(session_factory)
    dep = await _insertar_deployment(session_factory)

    claims = {
        "sub": "mdl-702",
        "iss": _ISS,
        "name": "Alumno Sin Claim Roles",
        "email": "alumno.sinrol@demo.test",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }

    async with session_factory() as s:
        usuario, creado = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado is True


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
    usuario.username = "lti:7:mdl-500"
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
# 5.6 — Endpoint /lti/launch: primer ingreso pide confirmación, reingreso loguea directo
# ---------------------------------------------------------------------------


def _armar_app_lti(session_factory, *, jwk, jwt_secret="test-jwt-secret-suficientemente-largo"):
    """Arma la app FastAPI + TestClient del router LTI, reusado por los tests HTTP."""
    cipher = SecretCipher(key=Fernet.generate_key().decode())
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
    return TestClient(app, follow_redirects=False)


def _setup_deployment_y_nonce(session_factory, *, deployment_id=_DEPLOYMENT_ID):
    """Limpia tablas LTI, inserta un deployment activo + un nonce fresco. Sync
    (usa asyncio.run) porque `session_factory` es una fixture module-scope sync."""

    async def _setup():
        async with session_factory() as s:
            await s.execute(text("DELETE FROM lti_provisioning_pendiente"))
            await s.execute(text("DELETE FROM inscripcion"))
            await s.execute(text("DELETE FROM lti_nonce"))
            await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
            await s.execute(text("DELETE FROM lti_deployment_confiable"))
            await s.execute(text("DELETE FROM lti_tool_key"))
            await s.commit()

        dep = LtiDeploymentConfiableModel(
            iss=_ISS, deployment_id=deployment_id, client_id=_CLIENT_ID,
            jwks_uri=f"{_ISS}/mod/lti/certs.php",
        )
        async with session_factory() as s:
            s.add(dep)
            await s.commit()

        nonce = secrets.token_urlsafe(16)
        state = secrets.token_urlsafe(16)
        async with session_factory() as s:
            s.add(LtiNonceModel(
                nonce=nonce, state=state, iss=_ISS,
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=5),
            ))
            await s.commit()
        return nonce, state

    return asyncio.run(_setup())


def test_launch_primer_ingreso_redirige_a_confirmar_sin_tokens(session_factory):
    """5.6 (fix 2026-08-19): el PRIMER ingreso (cuenta nueva) ya NO loguea
    directo — redirige a /lti-confirmar con un pendiente_id, SIN tokens. La
    cuenta todavía no existe hasta que se confirme."""
    nonce, state = _setup_deployment_y_nonce(session_factory)
    pem, jwk = _par_rsa()
    token = _firmar(pem, _claims(nonce=nonce, sub="mdl-900", email="nuevo900@demo.test"))

    client = _armar_app_lti(session_factory, jwk=jwk)
    r = client.post("/api/v1/lti/launch", data={"id_token": token, "state": state})

    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith("https://frontend.test/lti-confirmar#")
    fragment = location.split("#", 1)[1]
    assert "pendiente_id=" in fragment
    assert "access_token=" not in fragment  # todavia no se emitio nada

    huerfano = asyncio.run(
        _usuario_por_username(session_factory, f"lti:{_DEPLOYMENT_ID}:mdl-900")
    )
    assert huerfano is None  # la cuenta NO se creo todavia


def test_confirmar_provisioning_crea_cuenta_y_devuelve_tokens(session_factory):
    """El segundo paso (confirmación explícita) recién ahí crea la cuenta y
    emite la sesión, con los mismos claims que ya se validaron en /launch."""
    nonce, state = _setup_deployment_y_nonce(session_factory)
    pem, jwk = _par_rsa()
    token = _firmar(pem, _claims(nonce=nonce, sub="mdl-901", email="nuevo901@demo.test"))

    client = _armar_app_lti(session_factory, jwk=jwk)
    r = client.post("/api/v1/lti/launch", data={"id_token": token, "state": state})
    fragment = r.headers["location"].split("#", 1)[1]
    pendiente_id = dict(p.split("=") for p in fragment.split("&"))["pendiente_id"]

    r2 = client.post("/api/v1/lti/confirmar-provisioning", json={"pendiente_id": pendiente_id})
    assert r2.status_code == 200
    body = r2.json()
    assert body["access_token"]
    assert body["refresh_token"]

    creado = asyncio.run(
        _usuario_por_username(session_factory, f"lti:{_DEPLOYMENT_ID}:mdl-901")
    )
    assert creado is not None
    assert creado.email == "nuevo901@demo.test"


def test_confirmar_provisioning_uso_unico(session_factory):
    """El pendiente es de UN SOLO USO: confirmar dos veces la segunda falla
    (410), no crea una segunda cuenta ni reemite tokens."""
    nonce, state = _setup_deployment_y_nonce(session_factory)
    pem, jwk = _par_rsa()
    token = _firmar(pem, _claims(nonce=nonce, sub="mdl-902", email="nuevo902@demo.test"))

    client = _armar_app_lti(session_factory, jwk=jwk)
    r = client.post("/api/v1/lti/launch", data={"id_token": token, "state": state})
    fragment = r.headers["location"].split("#", 1)[1]
    pendiente_id = dict(p.split("=") for p in fragment.split("&"))["pendiente_id"]

    r2 = client.post("/api/v1/lti/confirmar-provisioning", json={"pendiente_id": pendiente_id})
    assert r2.status_code == 200

    r3 = client.post("/api/v1/lti/confirmar-provisioning", json={"pendiente_id": pendiente_id})
    assert r3.status_code == 410


def test_confirmar_provisioning_id_inexistente_da_410(session_factory):
    """Un pendiente_id que nunca existió (inventado) se rechaza igual, 410."""
    _setup_deployment_y_nonce(session_factory)
    pem, jwk = _par_rsa()
    client = _armar_app_lti(session_factory, jwk=jwk)

    r = client.post(
        "/api/v1/lti/confirmar-provisioning",
        json={"pendiente_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 410


def test_launch_reingreso_redirige_directo_con_tokens(session_factory):
    """Reingreso (cuenta LTI ya existente): sigue logueando directo, SIN pasar
    por confirmación — la fricción es solo para el primer ingreso."""
    nonce1, state1 = _setup_deployment_y_nonce(session_factory)
    pem, jwk = _par_rsa()
    claims_kwargs = dict(sub="mdl-903", email="reingreso903@demo.test")

    client = _armar_app_lti(session_factory, jwk=jwk)

    # Primer launch: pide confirmación, la confirma.
    token1 = _firmar(pem, _claims(nonce=nonce1, **claims_kwargs))
    r1 = client.post("/api/v1/lti/launch", data={"id_token": token1, "state": state1})
    fragment1 = r1.headers["location"].split("#", 1)[1]
    pendiente_id = dict(p.split("=") for p in fragment1.split("&"))["pendiente_id"]
    client.post("/api/v1/lti/confirmar-provisioning", json={"pendiente_id": pendiente_id})

    # Segundo launch (mismo sub → misma identidad LTI, ya existe): un nonce
    # nuevo (el anterior ya se consumió), pero SIN pasar por /lti-confirmar.
    async def _nuevo_nonce():
        nonce = secrets.token_urlsafe(16)
        state = secrets.token_urlsafe(16)
        async with session_factory() as s:
            s.add(LtiNonceModel(
                nonce=nonce, state=state, iss=_ISS,
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=5),
            ))
            await s.commit()
        return nonce, state

    nonce2, state2 = asyncio.run(_nuevo_nonce())
    token2 = _firmar(pem, _claims(nonce=nonce2, **claims_kwargs))
    r2 = client.post("/api/v1/lti/launch", data={"id_token": token2, "state": state2})

    assert r2.status_code == 302
    location2 = r2.headers["location"]
    assert location2.startswith("https://frontend.test/lti-login#")
    fragment2 = location2.split("#", 1)[1]
    assert "access_token=" in fragment2
    assert "refresh_token=" in fragment2


# ---------------------------------------------------------------------------
# 5.7 / 5.8 — Mapeo context_id → comision_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_context_id_mapeado_matricula_en_comision(session_factory):
    """5.7: context_id con mapeo configurado matricula al alumno en la comisión."""
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
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
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'lti:%'"))
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
