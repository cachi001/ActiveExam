"""Tests de integración — observaciones del proctor (C-15 tarea 3.2).

Insumo de la revision humana C-16: el proctor registra observaciones libres sobre
una sesion (multiples, append-only). Requiere Postgres real (sin mocks de DB).
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_observaciones_api.py -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.proctoring.conftest import auth_headers

# Observaciones = accion del proctor (proctor-only). El ``client`` por defecto va
# autenticado como estudiante (flujo del alumno); para escribir/leer observaciones
# mandamos un Bearer de rol proctor.
_PROCTOR = auth_headers(["coordinador"])  # c-76: rol proctor eliminado -> coordinador supervisa

pytestmark = pytest.mark.asyncio


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "examen", "etiqueta": "obs"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_crear_observacion_201(client: AsyncClient) -> None:
    """POST /sessions/{id}/observaciones (proctor) → 201 y persiste."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones",
        json={"texto": "El alumno miro fuera de pantalla 3 veces.", "proctor_actor": "proc-1"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["texto"] == "El alumno miro fuera de pantalla 3 veces."
    assert data["proctor_actor"] == "proc-1"
    assert "id" in data and "creada_en" in data


@pytest.mark.asyncio
async def test_listar_observaciones_orden_y_multiples(client: AsyncClient) -> None:
    """GET lista las observaciones asc por creada_en (multiples por sesion)."""
    session_id = await _crear_sesion(client)
    for txt in ("primera", "segunda", "tercera"):
        r = await client.post(
            f"/api/v1/proctoring/sessions/{session_id}/observaciones",
            json={"texto": txt},
            headers=_PROCTOR,
        )
        assert r.status_code == 201

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones", headers=_PROCTOR
    )
    assert resp.status_code == 200
    textos = [o["texto"] for o in resp.json()]
    assert textos == ["primera", "segunda", "tercera"]


@pytest.mark.asyncio
async def test_listar_observaciones_vacio(client: AsyncClient) -> None:
    """GET de una sesion sin observaciones → 200 lista vacia."""
    session_id = await _crear_sesion(client)
    resp = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones", headers=_PROCTOR
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_crear_observacion_sesion_inexistente_404(client: AsyncClient) -> None:
    """POST observacion sobre sesion inexistente → 404."""
    resp = await client.post(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/observaciones",
        json={"texto": "x"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_crear_observacion_texto_vacio_422(client: AsyncClient) -> None:
    """POST observacion con texto vacio → 422 (min_length=1)."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones",
        json={"texto": ""},
        headers=_PROCTOR,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_crear_observacion_campo_extra_422(client: AsyncClient) -> None:
    """POST observacion con campo extra → 422 (extra='forbid')."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones",
        json={"texto": "ok", "campo_extra": "no"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_observaciones_estudiante_403(client: AsyncClient) -> None:
    """RBAC: el estudiante NO puede escribir NI leer observaciones del proctor → 403.

    El ``client`` por defecto va autenticado como estudiante (sin header proctor)."""
    session_id = await _crear_sesion(client)
    post = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones",
        json={"texto": "intento del alumno"},
    )
    assert post.status_code == 403
    get = await client.get(f"/api/v1/proctoring/sessions/{session_id}/observaciones")
    assert get.status_code == 403


@pytest.mark.asyncio
async def test_observaciones_admin_puede(client: AsyncClient) -> None:
    """El admin (proctor_o_admin) tambien puede registrar observaciones → 201."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/observaciones",
        json={"texto": "revision admin"},
        headers=auth_headers(["admin_sistema"]),
    )
    assert resp.status_code == 201
