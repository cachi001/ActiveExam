"""Tests de integración de GET /api/v1/auth/me con nombre y apellido (C-62).

Verifica:
  - /auth/me devuelve nombre y apellido del usuario autenticado (lookup por subject).
  - /auth/me devuelve null en nombre y apellido si el usuario no tiene esos campos.

Tests con DB real (postgres:16-alpine). Se saltan si RUN_STACK_TESTS != 1.
Sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify_production
from app.infrastructure.auth.verifiers import build_hs256_verify
from app.main import create_app

_ISSUER = "activeexam-auth"
_AUD = "proctoring-api"
_SECRET_STR = "test-jwt-own-secret-256bits-at-least"
_SECRET_BYTES = _SECRET_STR.encode()

_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://app@db:5432/proctoring",
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "k",
    "STORAGE_SECRET_KEY": "s",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "KEYCLOAK_ISSUER": "http://keycloak:8080/realms/proctoring",
    "KEYCLOAK_JWKS_URL": "http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs",
    "JWT_AUDIENCE": _AUD,
    "JWT_OWN_SECRET": _SECRET_STR,
    "JWT_OWN_ISSUER": _ISSUER,
    "AUTH_PROVIDER": "jwt",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    app = create_app(settings)

    cache = JwksCache(lambda: {"keys": []}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({_ISSUER, settings.keycloak_issuer}),
        audience=_AUD,
    )
    verify_hs256 = build_hs256_verify_production(_SECRET_STR)
    verify_rs256 = build_hs256_verify(_SECRET_BYTES)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=verify_rs256,
        verify_fn_hs256=verify_hs256,
        own_issuer=_ISSUER,
        keycloak_issuer=settings.keycloak_issuer,
    )
    return TestClient(app)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_me_devuelve_nombre_y_apellido(client: TestClient) -> None:
    """Login con usuario que tiene nombre y apellido → /auth/me los devuelve."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415

    session_factory = client.app.state.session_factory
    if session_factory is None:
        pytest.skip("session_factory no disponible (sin DB)")

    async with session_factory() as session:
        usuario = UsuarioModel(
            id_institucional="test-me-user-con-nombre",
            email="test-me-nombre@demo.test",
            nombre="Ana",
            apellido="García",
            roles=["estudiante"],
            password_hash=hashear_password("TestPassword123"),
            auth_provider="local",
            attrs_federados={},
        )
        session.add(usuario)
        await session.commit()
        await session.refresh(usuario)
        usuario_id = usuario.id

    try:
        # Login para obtener un access token real (sub = usuario.id).
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "test-me-nombre@demo.test", "password": "TestPassword123"},
        )
        assert login_resp.status_code == 200, f"Login falló: {login_resp.json()}"
        access_token = login_resp.json()["access_token"]

        # Llamar a /auth/me con el token real.
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 200, f"/auth/me falló: {me_resp.json()}"
        body = me_resp.json()

        assert body["nombre"] == "Ana", f"nombre esperado 'Ana', recibido: {body.get('nombre')}"
        assert body["apellido"] == "García", f"apellido esperado 'García', recibido: {body.get('apellido')}"
        assert body["id_institucional"] == "test-me-user-con-nombre"
        assert "estudiante" in body["roles"]

    finally:
        async with session_factory() as session:
            from sqlalchemy import delete  # noqa: PLC0415
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.id == usuario_id)
            )
            await session.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_me_devuelve_null_cuando_nombre_y_apellido_son_null(client: TestClient) -> None:
    """Usuario con nombre=null y apellido=null → /auth/me devuelve null sin error 500."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415

    session_factory = client.app.state.session_factory
    if session_factory is None:
        pytest.skip("session_factory no disponible (sin DB)")

    async with session_factory() as session:
        usuario = UsuarioModel(
            id_institucional="test-me-user-sin-nombre",
            email="test-me-sin-nombre@demo.test",
            nombre=None,
            apellido=None,
            roles=["estudiante"],
            password_hash=hashear_password("TestPassword123"),
            auth_provider="local",
            attrs_federados={},
        )
        session.add(usuario)
        await session.commit()
        await session.refresh(usuario)
        usuario_id = usuario.id

    try:
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "test-me-sin-nombre@demo.test", "password": "TestPassword123"},
        )
        assert login_resp.status_code == 200, f"Login falló: {login_resp.json()}"
        access_token = login_resp.json()["access_token"]

        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 200, f"/auth/me devolvió error inesperado: {me_resp.json()}"
        body = me_resp.json()

        assert body["nombre"] is None, f"nombre debe ser null, recibido: {body.get('nombre')}"
        assert body["apellido"] is None, f"apellido debe ser null, recibido: {body.get('apellido')}"

    finally:
        async with session_factory() as session:
            from sqlalchemy import delete  # noqa: PLC0415
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.id == usuario_id)
            )
            await session.commit()
