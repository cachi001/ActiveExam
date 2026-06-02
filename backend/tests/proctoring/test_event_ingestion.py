"""Tests de integración — ingestión de eventos de proctoring slim.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de codigo).
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

# Screenshot minimo (1x1 PNG en base64) para tests que necesitan una imagen valida
_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_ingestar_evento_sin_screenshot_201(client: AsyncClient) -> None:
    """POST /sessions/{id}/events sin screenshot → 201 con veredicto 'no_evaluado'."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "bajo",
            "ts_cliente": "2026-06-02T10:00:00Z",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "evento_id" in data
    assert data["veredicto_reinferencia"] == "no_evaluado"
    assert data["screenshot_sha256"] is None
    assert data["face_count_servidor"] is None


@pytest.mark.asyncio
async def test_ingestar_evento_con_screenshot_sha256_poblado(client: AsyncClient) -> None:
    """POST /sessions/{id}/events con screenshot → screenshot_sha256 poblado."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "FACE_ABSENT",
            "severidad": "alto",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "screenshot_base64": _PNG_1X1_B64,
            "face_count_cliente": 0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    # sha256 debe ser string hex de 64 chars
    sha = data["screenshot_sha256"]
    assert sha is not None
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)

    # Verificar que el sha256 es correcto (sha256 de los bytes del string base64)
    expected = hashlib.sha256(_PNG_1X1_B64.encode("utf-8")).hexdigest()
    assert sha == expected


@pytest.mark.asyncio
async def test_ingestar_evento_con_payload(client: AsyncClient) -> None:
    """POST /sessions/{id}/events con payload → 201."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "MULTIPLE_FACES",
            "severidad": "critico",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "payload": {"face_count": 3, "confidence": 0.95},
            "face_count_cliente": 3,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "evento_id" in data
    assert data["veredicto_reinferencia"] in ("coincide", "discrepancia", "no_evaluado")


@pytest.mark.asyncio
async def test_ingestar_evento_sesion_inexistente_404(client: AsyncClient) -> None:
    """POST /sessions/{id}/events con sesion inexistente → 404."""
    resp = await client.post(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "bajo",
            "ts_cliente": "2026-06-02T10:00:00Z",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingestar_evento_severidad_invalida_422(client: AsyncClient) -> None:
    """POST /sessions/{id}/events con severidad invalida → 422."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "ultra",  # invalido
            "ts_cliente": "2026-06-02T10:00:00Z",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_respuesta_evento_incluye_veredicto_y_sha256(client: AsyncClient) -> None:
    """La respuesta de POST /events incluye veredicto_reinferencia, face_count_servidor, screenshot_sha256."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "FACE_ABSENT",
            "severidad": "alto",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "screenshot_base64": _PNG_1X1_B64,
            "face_count_cliente": 1,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "evento_id" in data
    assert "veredicto_reinferencia" in data
    assert "face_count_servidor" in data
    assert "screenshot_sha256" in data
    assert data["veredicto_reinferencia"] in ("coincide", "discrepancia", "no_evaluado")
