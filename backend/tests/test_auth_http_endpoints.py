"""Tests HTTP de auth en el borde FastAPI (C-06): 401/403/MFA + /auth/refresh.

Verifica el mapeo de los errores de dominio a HTTP en endpoints reales:
- sin Bearer -> 401; con principal sin rol -> 403; con rol y MFA -> OK.
- ``POST /auth/refresh`` rota; refresh ya rotado -> 401.

Inyecta un ``JwtValidator`` de prueba en ``app.state`` (HS256 stdlib), de modo que
no requiere PyJWT ni Keycloak. Requiere las deps de runtime (fastapi, httpx via
TestClient, pydantic_settings para ``Settings``); por eso comparte el patron de
``test_app_factory`` (construye ``Settings`` del entorno de test).
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

_SECRET = b"http-test-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"

_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://app@db:5432/proctoring",
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "k",
    "STORAGE_SECRET_KEY": "s",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "KEYCLOAK_ISSUER": _ISSUER,
    "KEYCLOAK_JWKS_URL": _ISSUER + "/protocol/openid-connect/certs",
    "JWT_AUDIENCE": _AUD,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    app = create_app(settings)

    # Inyecta un validador HS256 de test (sin PyJWT/Keycloak).
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuer=_ISSUER, audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )

    # Endpoint protegido de prueba: exige rol admin de examenes.
    protected = APIRouter()

    @protected.get("/solo-admin")
    async def solo_admin(
        principal: AuthenticatedPrincipal = Depends(require_roles(Rol.ADMIN_EXAMENES)),
    ) -> dict:
        return {"ok": True, "user": principal.id_institucional}

    app.include_router(protected, prefix="/api/v1/test")
    return TestClient(app)


def _token(roles, mfa=True, exp=9999999999) -> str:
    claims = {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "s",
        "preferred_username": "u1",
        "email": "u1@uni.edu",
        "exp": exp,
        "realm_access": {"roles": roles},
    }
    if mfa:
        claims["amr"] = ["otp"]
    return encode_hs256(claims, _SECRET)


def test_sin_bearer_devuelve_401(client: TestClient) -> None:
    resp = client.get("/api/v1/test/solo-admin")
    assert resp.status_code == 401


def test_rol_incorrecto_devuelve_403(client: TestClient) -> None:
    token = _token(["estudiante"])
    resp = client.get(
        "/api/v1/test/solo-admin", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_rol_correcto_devuelve_200(client: TestClient) -> None:
    token = _token(["admin_examenes"])
    resp = client.get(
        "/api/v1/test/solo-admin", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_token_invalido_devuelve_401(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/test/solo-admin", headers={"Authorization": "Bearer no-jwt"}
    )
    assert resp.status_code == 401


def test_refresh_rota_y_rechaza_reuso(client: TestClient) -> None:
    store = client.app.state.refresh_store
    original = store.issue()
    ok = client.post("/api/v1/auth/refresh", json={"refresh_token": original})
    assert ok.status_code == 200
    nuevo = ok.json()["refresh_token"]
    assert nuevo != original
    # Reuso del refresh ya rotado -> 401.
    reuso = client.post("/api/v1/auth/refresh", json={"refresh_token": original})
    assert reuso.status_code == 401


def test_me_devuelve_principal(client: TestClient) -> None:
    token = _token(["proctor"])
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id_institucional"] == "u1"
    assert "proctor" in body["roles"]
    assert body["mfa_satisfecho"] is True


def test_refresh_rechaza_campo_extra(client: TestClient) -> None:
    # Pydantic extra='forbid' (regla dura): campo no declarado -> 422.
    resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "x", "otro": "y"}
    )
    assert resp.status_code == 422
