"""C-75 §7.2 (refinamiento): definir contraseña inicial de un usuario LTI.

Un alumno provisionado JIT vía LTI tiene ``debe_cambiar_password=True`` pero NUNCA
recibió una contraseña temporal (se le generó una random no comunicada). El gate
"Definí tu contraseña" NO debe pedirle la actual: sólo la nueva. Con la sesión
(Bearer emitido tras un launch LTI válido) alcanza para probar identidad.

Comportamiento esperado (pedido del dueño):
  - 1er ingreso LTI → define contraseña (sin pedir la actual) → debe_cambiar=false.
  - Luego puede loguearse directo con usuario+contraseña (`POST /auth/login`).
  - 2do launch → entra directo (debe_cambiar_password ya es false).

DB real (regla dura #4). Usa el activeexam app completo (mismo emisor/validador que prod).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

_DB_URL_ACTIVEEXAM = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://proctoring:dev-only-change-me@localhost:5432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-activeexam")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY", "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
)

_ACTIVEEXAM_ENV = {
    "DATABASE_URL": _DB_URL_ACTIVEEXAM,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}


@pytest.fixture
def activeexam_client(monkeypatch: pytest.MonkeyPatch):
    """App mínima con SOLO el auth router (evita stats/matplotlib del activeexam completo).

    Cablea settings + session_factory + jwt_validator (HS256 del emisor propio) en
    app.state, que es lo único que los endpoints /auth/* consumen.
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL no seteada — test de integración omitido")
    from fastapi import FastAPI

    import app.config_activeexam as config_activeexam_module

    config_activeexam_module.get_activeexam_settings.cache_clear()
    for k, v in _ACTIVEEXAM_ENV.items():
        monkeypatch.setenv(k, v)
    settings = config_activeexam_module.get_activeexam_settings()

    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )
    from app.presentation.api.v1.auth.router import router as auth_router

    engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
    factory = create_activeexam_session_factory(engine)

    app_instance = FastAPI()
    app_instance.state.settings = settings
    app_instance.state.session_factory = factory
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({settings.jwt_own_issuer}),
        audience=settings.jwt_audience,
    )
    app_instance.state.jwt_validator = JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=build_hs256_verify(settings.jwt_own_secret.encode()),
    )
    app_instance.include_router(auth_router, prefix="/api/v1/auth")

    with TestClient(app_instance) as c:
        yield c
    config_activeexam_module.get_activeexam_settings.cache_clear()


def _url_async(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url


def _crear_usuario_lti(id_inst: str, email: str) -> str:
    """Crea un usuario LTI recién provisionado (debe_cambiar_password=True, pass random)."""
    import secrets

    from sqlalchemy import delete
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    async def _run():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.username == id_inst)
            )
            await session.commit()
            u = UsuarioModel(
                username=id_inst,
                email=email,
                roles=["estudiante"],
                password_hash=hashear_password(secrets.token_urlsafe(32)),
                auth_provider="lti",
                debe_cambiar_password=True,
                attrs_federados={},
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            uid = str(u.id)
        await engine.dispose()
        return uid

    return asyncio.run(_run())


def _token_propio(uid: str) -> str:
    """Emite un JWT de sesión propio para el usuario (mismo emisor que /auth/login)."""
    from sqlalchemy import select
    from app.config_activeexam import get_activeexam_settings
    from app.infrastructure.auth.own_issuer import emitir_jwt_propio
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    async def _run():
        s = get_activeexam_settings()
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            u = (
                await session.execute(select(UsuarioModel).where(UsuarioModel.id == uid))
            ).scalar_one()
            tok = emitir_jwt_propio(
                u,
                secret=s.jwt_own_secret,
                issuer=s.jwt_own_issuer,
                audience=s.jwt_audience,
                ttl_seconds=900,
            )
        await engine.dispose()
        return tok

    return asyncio.run(_run())


def _limpiar(id_inst: str) -> None:
    from sqlalchemy import delete
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    async def _run():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.username == id_inst)
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


_ID = "c75-lti-passwd"
_EMAIL = "c75-lti-passwd@demo.test"
_NUEVA = "MiClaveNueva123"


def test_lti_primer_set_sin_password_actual(activeexam_client):
    """El usuario LTI define su contraseña sin informar la actual → 200 y gate resuelto."""
    uid = _crear_usuario_lti(_ID, _EMAIL)
    try:
        token = _token_propio(uid)
        r = activeexam_client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_nueva": _NUEVA},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        # /auth/me refleja debe_cambiar_password=false y auth_provider=lti.
        me = activeexam_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).json()
        assert me["debe_cambiar_password"] is False
        assert me["auth_provider"] == "lti"
    finally:
        _limpiar(_ID)


def test_lti_puede_loguear_directo_tras_definir(activeexam_client):
    """Tras definir la contraseña, el alumno LTI puede loguearse directo (link/portal)."""
    uid = _crear_usuario_lti(_ID, _EMAIL)
    try:
        token = _token_propio(uid)
        activeexam_client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_nueva": _NUEVA},
            headers={"Authorization": f"Bearer {token}"},
        )
        r = activeexam_client.post(
            "/api/v1/auth/login", json={"username": _ID, "password": _NUEVA}
        )
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()
    finally:
        _limpiar(_ID)


def test_lti_segundo_cambio_exige_actual(activeexam_client):
    """Ya con contraseña definida (debe_cambiar=false), un cambio posterior SÍ exige la actual."""
    uid = _crear_usuario_lti(_ID, _EMAIL)
    try:
        token = _token_propio(uid)
        # Primer set.
        activeexam_client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_nueva": _NUEVA},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Segundo cambio sin la actual → 400.
        r = activeexam_client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_nueva": "OtraClave456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
    finally:
        _limpiar(_ID)
