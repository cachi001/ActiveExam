"""Test del healthcheck del modulo slim de proctoring.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_health_db_ok(client: AsyncClient) -> None:
    """GET /api/v1/proctoring/health con DB disponible → {status: ok, db: ok}."""
    resp = await client.get("/api/v1/proctoring/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
