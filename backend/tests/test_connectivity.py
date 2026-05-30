"""Smoke tests de CONECTIVIDAD contra DB, storage e IdP.

Verifica el Requirement "Conectividad verificada contra DB, storage e IdP".

REQUIERE EL STACK LEVANTADO (Docker Compose). Estos tests estan marcados
``@pytest.mark.requires_stack`` y se SALTAN salvo que ``RUN_STACK_TESTS=1`` este
en el entorno con el compose arriba. No mockean la base (regla dura de codigo:
tests sin mocks de DB) — golpean los servicios reales del stack local.

Comando de ejecucion (con el stack arriba):
    RUN_STACK_TESTS=1 pytest backend/tests/test_connectivity.py
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.requires_stack


def _require(env: str) -> str:
    value = os.environ.get(env)
    if not value:
        pytest.fail(f"Falta {env}: el stack debe exportar la config de conexion.")
    return value


def test_postgres_timescaledb_reachable() -> None:
    """Conecta a Postgres y verifica que la extension TimescaleDB esta instalada."""
    psycopg = pytest.importorskip("psycopg")
    dsn = _require("DATABASE_URL").replace("+asyncpg", "").replace("+psycopg", "")
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"
            )
            assert cur.fetchone() is not None, "TimescaleDB no esta habilitada (migracion 001)"


def test_minio_storage_reachable() -> None:
    """Verifica que el endpoint de MinIO/S3 responde."""
    requests = pytest.importorskip("requests")
    endpoint = _require("STORAGE_ENDPOINT")
    # MinIO expone /minio/health/live para liveness.
    resp = requests.get(f"{endpoint}/minio/health/live", timeout=5)
    assert resp.status_code == 200, "MinIO/S3 no responde el healthcheck"


def test_keycloak_idp_reachable() -> None:
    """Verifica que Keycloak responde su endpoint de configuracion OIDC."""
    requests = pytest.importorskip("requests")
    issuer = _require("KEYCLOAK_ISSUER")
    resp = requests.get(
        f"{issuer}/.well-known/openid-configuration", timeout=5
    )
    assert resp.status_code == 200, "Keycloak (IdP) no responde la config OIDC"
