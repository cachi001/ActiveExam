"""Tests de integracion — calibracion de mirada de la sesion (migracion 0108).

Descriptiva, NUNCA evidencia ni criterio de score (reglas duras #5/#6): solo
documenta con que cero se evaluo la mirada de esta sesion. Requiere Postgres
real (sin mocks de DB):
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_calibracion_sesion_api.py -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.proctoring.conftest import ALUMNO_DE_TEST, auth_headers

_ADMIN = auth_headers(["admin_sistema"])
_OTRO_ALUMNO = "22222222-2222-4222-8222-222222222222"

pytestmark = pytest.mark.asyncio


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "examen", "etiqueta": "calib"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


_CUATRO_PUNTOS = {
    "centro": {"x": 0.02, "y": -0.01},
    "rango_x": [-0.22, 0.24],
    "rango_y": [-0.55, 0.53],
    "origen": "paso_previo",
    "muestras_por_punto": 13,
}


async def test_guardar_calibracion_de_cuatro_puntos_200(client: AsyncClient) -> None:
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json=_CUATRO_PUNTOS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert data["calibracion"]["centro"] == {"x": 0.02, "y": -0.01}
    assert data["calibracion"]["rango_x"] == [-0.22, 0.24]
    assert data["calibracion"]["origen"] == "paso_previo"


async def test_guardar_calibracion_de_respaldo_sin_rango_200(client: AsyncClient) -> None:
    """El respaldo mide UN solo punto: rango_x/rango_y viajan None."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json={
            "centro": {"x": 0.1, "y": 0.0},
            "rango_x": None,
            "rango_y": None,
            "origen": "respaldo",
            "muestras_por_punto": 13,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["calibracion"]["rango_x"] is None
    assert resp.json()["calibracion"]["origen"] == "respaldo"


async def test_guardar_calibracion_sobrescribe_la_anterior(client: AsyncClient) -> None:
    """Recalibrar (reintentos antes de empezar) pisa la medicion previa."""
    session_id = await _crear_sesion(client)
    await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion", json=_CUATRO_PUNTOS
    )
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json={**_CUATRO_PUNTOS, "centro": {"x": 0.5, "y": 0.5}},
    )
    assert resp.status_code == 200
    assert resp.json()["calibracion"]["centro"] == {"x": 0.5, "y": 0.5}


async def test_guardar_calibracion_404_sesion_inexistente(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/calibracion",
        json=_CUATRO_PUNTOS,
    )
    assert resp.status_code == 404


async def test_guardar_calibracion_404_sesion_ajena(client: AsyncClient) -> None:
    """H1 (IDOR): la sesion de OTRO alumno no se puede calibrar por su id."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json=_CUATRO_PUNTOS,
        headers=auth_headers(
            ["estudiante"], subject=_OTRO_ALUMNO, username="otro-alumno", email="otro@test.local"
        ),
    )
    assert resp.status_code == 404


async def test_guardar_calibracion_origen_invalido_422(client: AsyncClient) -> None:
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json={**_CUATRO_PUNTOS, "origen": "quien_sabe"},
    )
    assert resp.status_code == 422


async def test_guardar_calibracion_campo_extra_422(client: AsyncClient) -> None:
    """extra='forbid' — regla dura de codigo."""
    session_id = await _crear_sesion(client)
    resp = await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion",
        json={**_CUATRO_PUNTOS, "veredicto": "fraude"},
    )
    assert resp.status_code == 422


async def test_detalle_surfacea_calibracion(client: AsyncClient) -> None:
    session_id = await _crear_sesion(client)

    antes = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_ADMIN
    )
    assert antes.status_code == 200
    assert antes.json()["calibracion"] is None

    await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion", json=_CUATRO_PUNTOS
    )

    despues = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_ADMIN
    )
    assert despues.status_code == 200
    assert despues.json()["calibracion"]["origen"] == "paso_previo"


async def test_calibracion_nunca_participa_del_score(client: AsyncClient) -> None:
    """Reglas duras #5/#6: guardar la calibracion no cambia el score de la sesion."""
    session_id = await _crear_sesion(client)
    antes = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_ADMIN
    )
    score_antes = antes.json()["score"]

    await client.patch(
        f"/api/v1/proctoring/sessions/{session_id}/calibracion", json=_CUATRO_PUNTOS
    )

    despues = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_ADMIN
    )
    assert despues.json()["score"] == score_antes
