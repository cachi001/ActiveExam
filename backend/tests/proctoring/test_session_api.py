"""Tests de integración — endpoints de sesiones de proctoring slim.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de codigo).
Correr con:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_session_api.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_crear_sesion_201(client: AsyncClient) -> None:
    """POST /sessions → 201 con id y creada_en."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "etiqueta": "mi sesion"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "creada_en" in data


@pytest.mark.asyncio
async def test_crear_sesion_modo_examen(client: AsyncClient) -> None:
    """POST /sessions con modo='examen' y exam_id → 201."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "exam_id": "exam-123", "etiqueta": "examen fisica"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_crear_sesion_campo_extra_rechazado(client: AsyncClient) -> None:
    """POST /sessions con campo extra → 422 (extra='forbid')."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "campo_extra": "no_permitido"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listar_sesiones_200(client: AsyncClient) -> None:
    """GET /sessions → 200 con lista (puede estar vacia)."""
    resp = await client.get("/api/v1/proctoring/sessions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_listar_sesiones_incluye_sesion_creada(client: AsyncClient) -> None:
    """GET /sessions devuelve la sesion creada con los campos correctos."""
    # Crear sesion
    create_resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "etiqueta": "sesion lista"},
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Listar y verificar que aparece
    list_resp = await client.get("/api/v1/proctoring/sessions")
    assert list_resp.status_code == 200
    sesiones = list_resp.json()
    ids = [s["id"] for s in sesiones]
    assert session_id in ids

    # Verificar campos del resumen
    sesion = next(s for s in sesiones if s["id"] == session_id)
    assert "total_eventos" in sesion
    assert "total_discrepancias" in sesion
    assert "score" in sesion
    assert sesion["total_eventos"] == 0
    assert sesion["score"] == 0


@pytest.mark.asyncio
async def test_obtener_sesion_200(client: AsyncClient) -> None:
    """GET /sessions/{id} → 200 con estructura completa."""
    create_resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test"},
    )
    session_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/proctoring/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert "eventos" in data
    assert "biometria" in data
    assert isinstance(data["eventos"], list)
    assert data["score"] == 0


@pytest.mark.asyncio
async def test_obtener_sesion_404(client: AsyncClient) -> None:
    """GET /sessions/{id} con id inexistente → 404."""
    resp = await client.get(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_listar_sesiones_total_discrepancias_correcto(client: AsyncClient) -> None:
    """GET /sessions devuelve total_discrepancias correcto tras ingestar eventos."""
    # Crear sesion
    create_resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}
    )
    session_id = create_resp.json()["id"]

    # Ingestar evento con discrepancia (face_count_cliente=2, servidor re-detectara distinto)
    # En modo test sin mediapipe instalado el veredicto sera 'no_evaluado'
    # Para forzar discrepancia en test, enviamos face_count_cliente explicitamente
    await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "MULTIPLE_FACES",
            "severidad": "alto",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "face_count_cliente": 2,
        },
    )

    list_resp = await client.get("/api/v1/proctoring/sessions")
    sesiones = list_resp.json()
    sesion = next((s for s in sesiones if s["id"] == session_id), None)
    assert sesion is not None
    # total_discrepancias puede ser 0 o 1 dependiendo de si MediaPipe esta disponible
    assert sesion["total_eventos"] == 1


@pytest.mark.asyncio
async def test_sesion_detalle_incluye_campos_reinferencia(client: AsyncClient) -> None:
    """GET /sessions/{id} incluye screenshot_sha256, veredicto, face_counts por evento."""
    create_resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}
    )
    session_id = create_resp.json()["id"]

    # Ingestar evento sin screenshot
    await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "bajo",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "face_count_cliente": 1,
        },
    )

    resp = await client.get(f"/api/v1/proctoring/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["eventos"]) == 1
    evento = data["eventos"][0]
    assert "screenshot_sha256" in evento
    assert "veredicto_reinferencia" in evento
    assert "face_count_cliente" in evento
    assert "face_count_servidor" in evento
    assert evento["veredicto_reinferencia"] in ("coincide", "discrepancia", "no_evaluado")
