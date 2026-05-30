"""Smoke tests del app factory y el router base (sin servicios externos).

Verifica el Requirement: "FastAPI mono-hilo escalado horizontalmente" (la app se
construye via factory) y que el router base ``/api/v1`` expone healthchecks.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
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
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)
    return Settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    return TestClient(app)


def test_create_app_returns_fastapi_instance(settings: Settings) -> None:
    app = create_app(settings)
    assert isinstance(app, FastAPI)
    assert app.title == settings.app_name


def test_liveness_healthcheck_ok(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readiness_healthcheck_responds(client: TestClient) -> None:
    # Readiness puede reportar dependencias caidas (no hay stack en este test),
    # pero el endpoint DEBE responder para que Nginx pueda hacer pooling (DD-10).
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body


def test_metrics_endpoint_exposes_prometheus(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    # Formato de exposicion Prometheus (texto plano con HELP/TYPE).
    assert "# HELP" in resp.text or "# TYPE" in resp.text
