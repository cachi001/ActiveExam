"""Tests de integración — cierre forzado de sesion por el proctor (C-15 tarea 3.3).

Operativo, NO disciplinario (regla dura #5: el sistema nunca sanciona; el veredicto
es HUMANO en C-16). El audit trail vive en la propia fila (cierre_forzado_*).
Requiere Postgres real (sin mocks de DB).
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_cierre_forzado_api.py -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from tests.proctoring.conftest import auth_headers

_PROCTOR = auth_headers(["proctor"])

pytestmark = pytest.mark.asyncio


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "examen", "etiqueta": "cf"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_cerrar_forzado_200(client: AsyncClient) -> None:
    """PATCH /sessions/{id}/cerrar-forzado (proctor) → 200, setea finalizada_en + audit."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": "Conducta sospechosa sostenida.", "proctor_actor": "proc-9"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert data["finalizada_en"] is not None
    assert data["cierre_forzado_en"] is not None
    assert data["cierre_forzado_por"] == "proc-9"
    assert data["cierre_forzado_motivo"] == "Conducta sospechosa sostenida."


@pytest.mark.asyncio
async def test_cerrar_forzado_idempotente(client: AsyncClient) -> None:
    """Segundo cierre forzado NO muta el audit del primero (inmutable)."""
    session_id = await _crear_sesion(client)
    r1 = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": "primero", "proctor_actor": "proc-A"},
        headers=_PROCTOR,
    )
    assert r1.status_code == 200
    primero = r1.json()

    r2 = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": "segundo intento", "proctor_actor": "proc-B"},
        headers=_PROCTOR,
    )
    assert r2.status_code == 200
    segundo = r2.json()
    # El audit del PRIMER cierre se preserva (no lo pisa el segundo).
    assert segundo["cierre_forzado_por"] == "proc-A"
    assert segundo["cierre_forzado_motivo"] == "primero"
    assert segundo["cierre_forzado_en"] == primero["cierre_forzado_en"]


@pytest.mark.asyncio
async def test_cerrar_forzado_no_disciplinario_decision_none(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """L2.5: el cierre forzado NO toca ``decision`` (veredicto HUMANO de C-16)."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": "operativo"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 200

    # Verificacion contra la DB real: decision/decision_actor siguen en NULL.
    row = (
        await db_session.execute(
            select(ProctoringSessionModel).where(
                ProctoringSessionModel.id == session_id
            )
        )
    ).scalar_one()
    assert row.decision is None
    assert row.decision_actor is None
    assert row.cierre_forzado_motivo == "operativo"


@pytest.mark.asyncio
async def test_cerrar_forzado_404(client: AsyncClient) -> None:
    """PATCH cierre forzado sobre sesion inexistente → 404."""
    resp = await client.patch(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/cerrar-forzado",
        json={"motivo": "x"},
        headers=_PROCTOR,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cerrar_forzado_motivo_vacio_422(client: AsyncClient) -> None:
    """PATCH cierre forzado con motivo vacio → 422 (motivo obligatorio)."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": ""},
        headers=_PROCTOR,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cerrar_forzado_estudiante_403(client: AsyncClient) -> None:
    """RBAC: el estudiante NO puede forzar el cierre → 403."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/cerrar-forzado",
        json={"motivo": "intento alumno"},
    )
    assert resp.status_code == 403
