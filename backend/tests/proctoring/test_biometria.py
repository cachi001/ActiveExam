"""Tests de integración — endpoint de biometria de proctoring slim.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de codigo).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_guardar_biometria_liveness_ok(client: AsyncClient) -> None:
    """POST /sessions/{id}/biometria con liveness_ok=True → 200 {ok: true}."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/biometria",
        json={
            "liveness_ok": True,
            "retos_resueltos": ["parpadeo", "giro_izquierda"],
            "resultado": "verificado",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_guardar_biometria_liveness_nok(client: AsyncClient) -> None:
    """POST /sessions/{id}/biometria con liveness_ok=False → 200 {ok: true}."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/biometria",
        json={
            "liveness_ok": False,
            "retos_resueltos": [],
            "resultado": "rechazado",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_guardar_biometria_sesion_inexistente_404(client: AsyncClient) -> None:
    """POST /sessions/{id}/biometria con sesion inexistente → 404."""
    resp = await client.post(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/biometria",
        json={
            "liveness_ok": True,
            "retos_resueltos": [],
            "resultado": "verificado",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_guardar_biometria_con_embedding(client: AsyncClient) -> None:
    """POST /sessions/{id}/biometria con embedding (dato sensible) → 200."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/biometria",
        json={
            "liveness_ok": True,
            "retos_resueltos": ["sonrisa"],
            "embedding": "base64_embedding_simulado",  # dato sensible Ley 25.326
            "resultado": "verificado",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_biometria_aparece_en_detalle_sesion(client: AsyncClient) -> None:
    """El resultado biometrico aparece en GET /sessions/{id}."""
    session_id = await _crear_sesion(client)
    await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/biometria",
        json={
            "liveness_ok": True,
            "retos_resueltos": ["parpadeo"],
            "resultado": "verificado",
        },
    )
    resp = await client.get(f"/api/v1/proctoring/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["biometria"] is not None
    assert data["biometria"]["liveness_ok"] is True
    assert data["biometria"]["resultado"] == "verificado"
