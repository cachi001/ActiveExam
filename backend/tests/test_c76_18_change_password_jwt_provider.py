"""c-76 §18: PUT /auth/change-password debe aceptar auth_provider='jwt'.

Bug: la migracion 0076 renombro el default de auth_provider de 'keycloak' a
'jwt' (limpieza de Keycloak), pero el endpoint de cambio de contrasena propio
seguia validando solo contra ('local', 'lti') -> 403 para toda cuenta con el
provider actual por default (el 100% de las cuentas sembradas, admin incluido).

DB real (regla dura #4).
"""

from __future__ import annotations

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


def _url_async(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


@pytest.fixture
def activeexam_client(monkeypatch: pytest.MonkeyPatch):
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL no seteada — test de integracion omitido")
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


async def _crear_usuario(username: str, email: str, *, auth_provider: str, password: str) -> str:
    from sqlalchemy import delete

    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
    factory = create_activeexam_session_factory(engine)
    async with factory() as session:
        await session.execute(delete(UsuarioModel).where(UsuarioModel.username == username))
        await session.commit()
        u = UsuarioModel(
            username=username,
            email=email,
            roles=["estudiante"],
            password_hash=hashear_password(password),
            auth_provider=auth_provider,
            debe_cambiar_password=False,
            attrs_federados={},
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
        uid = str(u.id)
    await engine.dispose()
    return uid


def _token_para(client: TestClient, uid: str) -> str:
    """Emite un Bearer valido para `uid` usando el mismo emisor HS256 que el validador."""
    import jwt as pyjwt

    settings = client.app.state.settings
    payload = {
        "sub": uid,
        "iss": settings.jwt_own_issuer,
        "aud": settings.jwt_audience,
    }
    import time

    payload["iat"] = int(time.time())
    payload["exp"] = int(time.time()) + 3600
    return pyjwt.encode(payload, settings.jwt_own_secret, algorithm="HS256")


def test_cambiar_contrasena_auth_provider_jwt_no_da_403(activeexam_client):
    """RED antes del fix: auth_provider='jwt' (el default real post-Keycloak) debe
    poder cambiar su contrasena con la clave actual correcta -> 200, NUNCA 403."""
    import asyncio

    uid = asyncio.run(
        _crear_usuario("jwtprov1", "jwtprov1@test.local", auth_provider="jwt", password="Clave123")
    )
    token = _token_para(activeexam_client, uid)

    resp = activeexam_client.put(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"contrasena_actual": "Clave123", "contrasena_nueva": "Clave1234"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def test_cambiar_contrasena_provider_no_gestionado_sigue_403(activeexam_client):
    """Triangulacion: un provider NO contemplado (ej. legado/desconocido) sigue
    rechazado — el fix no abre la puerta a cualquier auth_provider."""
    import asyncio

    uid = asyncio.run(
        _crear_usuario(
            "otroprov1", "otroprov1@test.local", auth_provider="keycloak", password="Clave123"
        )
    )
    token = _token_para(activeexam_client, uid)

    resp = activeexam_client.put(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"contrasena_actual": "Clave123", "contrasena_nueva": "Clave1234"},
    )
    assert resp.status_code == 403, resp.text
