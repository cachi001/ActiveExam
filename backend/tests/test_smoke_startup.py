"""Smoke tests de arranque (sin servicios externos).

Verifica el Requirement "Smoke tests de arranque y conectividad":
el stack levanta (la app se construye) y los healthchecks responden OK.
Estos no necesitan DB/storage/IdP: prueban que el proceso arranca y sirve.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://app@db:5432/proctoring",
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "test-access",
    "STORAGE_SECRET_KEY": "test-secret",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "KEYCLOAK_ISSUER": "http://keycloak:8080/realms/proctoring",
    "KEYCLOAK_JWKS_URL": "http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs",
    "JWT_AUDIENCE": "proctoring-api",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)
    return TestClient(create_app(Settings()))


def test_app_boots_and_serves_openapi(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "proctoring-api"


def test_liveness_is_green_on_boot(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readiness_endpoint_is_reachable_on_boot(client: TestClient) -> None:
    resp = client.get("/api/v1/health/ready")
    # Sin stack las dependencias estan caidas: 503 esperado, pero responde.
    assert resp.status_code in (200, 503)
    assert set(resp.json()["checks"]) == {"database", "storage", "identity_provider"}
