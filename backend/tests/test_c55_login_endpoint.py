"""Tests de integración de POST /api/v1/auth/login (C-55).

Verifica:
  - Login exitoso con credenciales válidas → 200 + access_token + refresh_token.
  - Password incorrecto → 401 con mensaje genérico (igual que usuario inexistente).
  - Usuario sin password_hash → 401 con mensaje genérico.
  - Timing-safe: el mensaje de error es IDENTICO en todos los casos de fallo.

Requiere el stack de DB levantado (RUN_STACK_TESTS=1).
Los tests que tocan la DB NO mockean la base — usan una sesión async real.

NOTA: estos tests se saltan automáticamente si RUN_STACK_TESTS != 1.
Para correrlos: export RUN_STACK_TESTS=1 con Postgres levantado y migración 0006 aplicada.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
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

    # Inyectar validador de test (sin PyJWT/Keycloak).
    cache = JwksCache(lambda: {"keys": []}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({_ISSUER, settings.keycloak_issuer}),
        audience=_AUD,
    )
    from app.infrastructure.auth.verifiers import build_hs256_verify_production  # noqa: PLC0415
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


@pytest.fixture
async def usuario_con_password(client: TestClient) -> dict:
    """Crea un usuario con password_hash en la DB de test."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415
    session_factory = client.app.state.session_factory
    if session_factory is None:
        pytest.skip("session_factory no disponible (sin DB)")

    async with session_factory() as session:
        usuario = UsuarioModel(
            id_institucional="test-login-user",
            email="test-login@demo.test",
            roles=["estudiante"],
            password_hash=hashear_password("TestPassword123"),
            auth_provider="local",
            attrs_federados={},
        )
        session.add(usuario)
        await session.commit()
        await session.refresh(usuario)
    yield {"id": usuario.id, "email": "test-login@demo.test", "id_institucional": "test-login-user"}

    # Cleanup
    async with session_factory() as session:
        from sqlalchemy import delete  # noqa: PLC0415
        await session.execute(delete(UsuarioModel).where(UsuarioModel.id == usuario.id))
        await session.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_login_exitoso(client: TestClient, usuario_con_password: dict) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": usuario_con_password["email"], "password": "TestPassword123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "Bearer"


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_login_password_incorrecto_401(client: TestClient, usuario_con_password: dict) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": usuario_con_password["email"], "password": "PasswordMalo999"},
    )
    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail == "Credenciales inválidas."


@pytest.mark.requires_stack
def test_login_usuario_inexistente_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "noexiste@demo.test", "password": "CualquierPass123"},
    )
    assert resp.status_code == 401
    # Mensaje genérico — mismo que password incorrecto (timing-safe a nivel msg).
    assert resp.json()["detail"] == "Credenciales inválidas."


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_login_usuario_sin_password_hash_401(client: TestClient) -> None:
    """Usuario Keycloak (sin password_hash) → 401 con mismo mensaje genérico."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415
    session_factory = client.app.state.session_factory
    if session_factory is None:
        pytest.skip("session_factory no disponible (sin DB)")

    async with session_factory() as session:
        usuario = UsuarioModel(
            id_institucional="test-kc-user",
            email="test-kc@demo.test",
            roles=["estudiante"],
            password_hash=None,  # sin credencial local
            auth_provider="keycloak",
            attrs_federados={},
        )
        session.add(usuario)
        await session.commit()
        usuario_id = usuario.id

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "test-kc@demo.test", "password": "CualquierPass123"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciales inválidas."

    # Cleanup.
    async with session_factory() as session:
        from sqlalchemy import delete  # noqa: PLC0415
        await session.execute(delete(UsuarioModel).where(UsuarioModel.id == usuario_id))
        await session.commit()


def test_login_rechaza_campo_extra(client: TestClient) -> None:
    """Pydantic extra='forbid': campo no declarado → 422."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "u", "password": "p", "extra_field": "x"},
    )
    assert resp.status_code == 422
