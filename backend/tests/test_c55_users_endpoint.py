"""Tests de POST /api/v1/users/ (C-55, D8).

Verifica:
  - Creación exitosa por admin_sistema → 201.
  - Rechazo por rol incorrecto (no admin_sistema) → 403.
  - Email duplicado → 409 Conflict.
  - Password < 8 chars → 422.
  - Campo extra en body → 422.

Los tests de creación real requieren DB (requires_stack).
Los tests de validación de schema (422) son unitarios (sin DB).
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.main import create_app
from app.presentation.api.v1.auth.dependencies import require_roles

_SECRET = b"test-secret-users"
_ISSUER = "activeexam-auth"
_AUD = "proctoring-api"

_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://app@db:5432/proctoring",
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "k",
    "STORAGE_SECRET_KEY": "s",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "KEYCLOAK_ISSUER": "http://keycloak:8080/realms/proctoring",
    "KEYCLOAK_JWKS_URL": "http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs",
    "JWT_AUDIENCE": _AUD,
    "JWT_OWN_SECRET": _SECRET.decode(),
    "JWT_OWN_ISSUER": _ISSUER,
    "AUTH_PROVIDER": "jwt",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


def _token(roles: list[str]) -> str:
    claims = {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "test-sub",
        "preferred_username": "testuser",
        "email": "test@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }
    return encode_hs256(claims, _SECRET)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    app = create_app(settings)

    # Inyectar validador de test.
    cache = JwksCache(lambda: {"keys": []}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({_ISSUER, settings.keycloak_issuer}),
        audience=_AUD,
    )
    verify = build_hs256_verify(_SECRET)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=verify,
        verify_fn_hs256=verify,
        own_issuer=_ISSUER,
        keycloak_issuer=settings.keycloak_issuer,
    )
    return TestClient(app)


# ---- Validaciones de schema (sin DB) ----------------------------------------

def test_password_corto_rechazado_422(client: TestClient) -> None:
    """Password < 8 chars → 422 (validación Pydantic)."""
    token = _token(["admin_sistema"])
    resp = client.post(
        "/api/v1/users/",
        json={
            "id_institucional": "u1",
            "email": "u1@uni.edu",
            "password": "corto",
            "roles": ["estudiante"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_campo_extra_rechazado_422(client: TestClient) -> None:
    """extra='forbid': campo no declarado → 422."""
    token = _token(["admin_sistema"])
    resp = client.post(
        "/api/v1/users/",
        json={
            "id_institucional": "u1",
            "email": "u1@uni.edu",
            "password": "ValidPassword123",
            "roles": ["estudiante"],
            "campo_extra": "x",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_sin_bearer_devuelve_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/users/",
        json={"id_institucional": "u1", "email": "u1@uni.edu", "password": "ValidPassword123", "roles": ["estudiante"]},
    )
    assert resp.status_code == 401


def test_rol_incorrecto_devuelve_403(client: TestClient) -> None:
    token = _token(["proctor"])
    resp = client.post(
        "/api/v1/users/",
        json={"id_institucional": "u1", "email": "u1@uni.edu", "password": "ValidPassword123", "roles": ["estudiante"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---- Tests con DB (requires_stack) ------------------------------------------

@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_creacion_exitosa_por_admin(client: TestClient) -> None:
    """Creación exitosa → 201 con los datos del usuario."""
    if client.app.state.session_factory is None:
        pytest.skip("Sin DB disponible")
    token = _token(["admin_sistema"])
    resp = client.post(
        "/api/v1/users/",
        json={
            "id_institucional": "test-nuevo-user-001",
            "email": "nuevo-user-001@demo.test",
            "password": "ValidPassword123",
            "roles": ["estudiante"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id_institucional"] == "test-nuevo-user-001"
    assert body["auth_provider"] == "local"

    # Cleanup.
    from sqlalchemy import delete  # noqa: PLC0415
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415
    async with client.app.state.session_factory() as session:
        await session.execute(delete(UsuarioModel).where(UsuarioModel.id == body["id"]))
        await session.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_email_duplicado_409(client: TestClient) -> None:
    """Email duplicado → 409 Conflict."""
    if client.app.state.session_factory is None:
        pytest.skip("Sin DB disponible")
    token = _token(["admin_sistema"])
    body = {
        "id_institucional": "test-dup-user-002",
        "email": "dup-user-002@demo.test",
        "password": "ValidPassword123",
        "roles": ["estudiante"],
    }
    r1 = client.post("/api/v1/users/", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/users/",
        json={**body, "id_institucional": "test-dup-user-002b"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409

    # Cleanup.
    from sqlalchemy import delete  # noqa: PLC0415
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: PLC0415
    async with client.app.state.session_factory() as session:
        await session.execute(delete(UsuarioModel).where(UsuarioModel.id == r1.json()["id"]))
        await session.commit()
