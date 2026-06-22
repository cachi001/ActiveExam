"""Tests de integracion — flujo de pausa autorizada (C-15 6.3). Postgres real, sin mocks."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"


async def _crear_sesion(client: AsyncClient, etiqueta: str | None = None) -> str:
    body = {"modo": "test"}
    if etiqueta is not None:
        body["etiqueta"] = etiqueta
    resp = await client.post(f"{_BASE}/sessions", json=body)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _solicitar(client: AsyncClient, sid: str, motivo: str = "ir al bano") -> str:
    resp = await client.post(f"{_BASE}/sessions/{sid}/pausas", json={"motivo": motivo})
    assert resp.status_code == 201
    return resp.json()["id"]


# --- POST solicitar ---


async def test_post_pausa_201(client: AsyncClient) -> None:
    """POST /sessions/{id}/pausas → 201 estado 'solicitada'."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "ir al bano"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert set(data) == {"id", "estado", "motivo", "solicitada_en"}
    assert data["estado"] == "solicitada"
    assert data["motivo"] == "ir al bano"


async def test_post_pausa_sesion_inexistente_404(client: AsyncClient) -> None:
    """Sesion inexistente → 404 (edge)."""
    resp = await client.post(
        f"{_BASE}/sessions/00000000-0000-0000-0000-000000000000/pausas",
        json={"motivo": "x"},
    )
    assert resp.status_code == 404


async def test_post_pausa_campo_extra_422(client: AsyncClient) -> None:
    """Campo extra → 422 (extra='forbid')."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "x", "evil": 1}
    )
    assert resp.status_code == 422


# --- GET por sesion ---


async def test_get_pausas_de_sesion_desc(client: AsyncClient) -> None:
    """GET /sessions/{id}/pausas lista desc por solicitada_en con todos los campos."""
    sid = await _crear_sesion(client)
    await _solicitar(client, sid, "primera")
    await _solicitar(client, sid, "segunda")

    resp = await client.get(f"{_BASE}/sessions/{sid}/pausas")
    assert resp.status_code == 200
    pausas = resp.json()
    assert len(pausas) == 2
    assert pausas[0]["motivo"] == "segunda"  # mas reciente primero
    campos = {
        "id", "motivo", "estado", "solicitada_en", "resuelta_en",
        "proctor_actor", "inicio_en", "fin_en",
    }
    assert set(pausas[0]) == campos


async def test_get_pausas_de_sesion_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get(
        f"{_BASE}/sessions/00000000-0000-0000-0000-000000000000/pausas"
    )
    assert resp.status_code == 404


# --- GET pendientes (poll del proctor) ---


async def test_get_pausas_pendientes_solo_solicitadas(client: AsyncClient) -> None:
    """GET /pausas/pendientes devuelve solo 'solicitada' de TODAS las sesiones."""
    sid1 = await _crear_sesion(client, etiqueta="examen-A")
    sid2 = await _crear_sesion(client, etiqueta="examen-B")
    p1 = await _solicitar(client, sid1, "m1")
    await _solicitar(client, sid2, "m2")
    # Aprobar p1 → ya no debe aparecer en pendientes
    await client.patch(f"{_BASE}/pausas/{p1}", json={"accion": "aprobar", "proctor_actor": "doc"})

    resp = await client.get(f"{_BASE}/pausas/pendientes")
    assert resp.status_code == 200
    pendientes = resp.json()
    assert len(pendientes) == 1
    item = pendientes[0]
    assert set(item) >= {"id", "session_id", "motivo", "solicitada_en"}
    assert item["session_id"] == sid2
    assert item["motivo"] == "m2"
    assert item["etiqueta"] == "examen-B"


# --- PATCH resolver ---


async def test_patch_aprobar_abre_ventana(client: AsyncClient) -> None:
    """aprobar → estado 'aprobada', resuelta_en e inicio_en seteados, proctor_actor."""
    sid = await _crear_sesion(client)
    pid = await _solicitar(client, sid)
    resp = await client.patch(
        f"{_BASE}/pausas/{pid}", json={"accion": "aprobar", "proctor_actor": "doc-99"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "aprobada"
    assert data["resuelta_en"] is not None
    assert data["inicio_en"] is not None
    assert data["proctor_actor"] == "doc-99"
    assert data["fin_en"] is None


async def test_patch_rechazar_no_abre_ventana(client: AsyncClient) -> None:
    """rechazar → estado 'rechazada', resuelta_en y proctor_actor set, inicio_en None (edge)."""
    sid = await _crear_sesion(client)
    pid = await _solicitar(client, sid)
    resp = await client.patch(
        f"{_BASE}/pausas/{pid}", json={"accion": "rechazar", "proctor_actor": "doc-1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "rechazada"
    assert data["resuelta_en"] is not None
    assert data["proctor_actor"] == "doc-1"
    assert data["inicio_en"] is None


async def test_patch_resolver_no_solicitada_409(client: AsyncClient) -> None:
    """Resolver una pausa que ya no esta 'solicitada' → 409 (edge)."""
    sid = await _crear_sesion(client)
    pid = await _solicitar(client, sid)
    await client.patch(f"{_BASE}/pausas/{pid}", json={"accion": "aprobar", "proctor_actor": "d"})
    # Segundo intento sobre la misma pausa ya aprobada
    resp = await client.patch(
        f"{_BASE}/pausas/{pid}", json={"accion": "rechazar", "proctor_actor": "d"}
    )
    assert resp.status_code == 409


async def test_patch_resolver_inexistente_404(client: AsyncClient) -> None:
    resp = await client.patch(
        f"{_BASE}/pausas/00000000-0000-0000-0000-000000000000",
        json={"accion": "aprobar", "proctor_actor": None},
    )
    assert resp.status_code == 404


# --- PATCH finalizar ---


async def test_patch_finalizar_cierra_ventana(client: AsyncClient) -> None:
    """finalizar una pausa aprobada → estado 'finalizada', fin_en seteado."""
    sid = await _crear_sesion(client)
    pid = await _solicitar(client, sid)
    await client.patch(f"{_BASE}/pausas/{pid}", json={"accion": "aprobar", "proctor_actor": "d"})
    resp = await client.patch(f"{_BASE}/pausas/{pid}/finalizar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "finalizada"
    assert data["fin_en"] is not None


async def test_patch_finalizar_no_aprobada_409(client: AsyncClient) -> None:
    """Finalizar una pausa que no esta 'aprobada' → 409 (edge)."""
    sid = await _crear_sesion(client)
    pid = await _solicitar(client, sid)  # estado 'solicitada'
    resp = await client.patch(f"{_BASE}/pausas/{pid}/finalizar")
    assert resp.status_code == 409


async def test_patch_finalizar_inexistente_404(client: AsyncClient) -> None:
    resp = await client.patch(
        f"{_BASE}/pausas/00000000-0000-0000-0000-000000000000/finalizar"
    )
    assert resp.status_code == 404
