"""Tests de carga de config twelve-factor (sin servicios externos).

Verifica el Requirement: "Configuracion por entorno con secretos via Vault/tmpfs"
y "La app falla cierre si falta config requerida" (twelve-factor-config spec).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

# Conjunto minimo de env vars requeridas para que la app arranque.
_REQUIRED_ENV: dict[str, str] = {
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


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)


def test_settings_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings()

    assert str(settings.database_url).startswith("postgresql")
    assert settings.storage_endpoint == "http://minio:9000"
    assert settings.keycloak_issuer.endswith("/realms/proctoring")
    assert settings.otel_exporter_otlp_endpoint == "http://tempo:4317"


def test_settings_fails_explicitly_when_required_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twelve-factor: sin default inseguro. Falta DATABASE_URL => falla al arrancar."""
    _clear_env(monkeypatch)
    for key, value in _REQUIRED_ENV.items():
        if key == "DATABASE_URL":
            continue  # omitida a proposito
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unknown_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """extra='forbid': la config rechaza variables no declaradas mal tipeadas."""
    _clear_env(monkeypatch)
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(unexpected_field="boom")


def test_no_insecure_defaults_for_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los secretos NO tienen default: deben venir del entorno (Vault/tmpfs)."""
    _clear_env(monkeypatch)
    for key, value in _REQUIRED_ENV.items():
        if key == "STORAGE_SECRET_KEY":
            continue
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings()
