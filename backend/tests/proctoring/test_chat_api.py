"""Tests de integracion — chat bidireccional (C-15 6.2). Postgres real, sin mocks de DB."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(f"{_BASE}/sessions", json={"modo": "test"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_post_chat_201(client: AsyncClient) -> None:
    """POST /sessions/{id}/chat → 201 con id, autor, texto, creado_en."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "hola profe"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert set(data) == {"id", "autor", "texto", "creado_en"}
    assert data["autor"] == "alumno"
    assert data["texto"] == "hola profe"


async def test_post_chat_proctor_201(client: AsyncClient) -> None:
    """autor='proctor' tambien es valido (happy path #2)."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "proctor", "texto": "te veo, segui"},
    )
    assert resp.status_code == 201
    assert resp.json()["autor"] == "proctor"


async def test_post_chat_autor_invalido_422(client: AsyncClient) -> None:
    """autor fuera de {alumno, proctor} → 422 (edge)."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "administrador", "texto": "x"},
    )
    assert resp.status_code == 422


async def test_post_chat_campo_extra_422(client: AsyncClient) -> None:
    """Campo extra → 422 (extra='forbid')."""
    sid = await _crear_sesion(client)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "x", "evil": 1},
    )
    assert resp.status_code == 422


async def test_post_chat_sesion_inexistente_404(client: AsyncClient) -> None:
    """Sesion inexistente → 404 (edge)."""
    resp = await client.post(
        f"{_BASE}/sessions/00000000-0000-0000-0000-000000000000/chat",
        json={"autor": "alumno", "texto": "x"},
    )
    assert resp.status_code == 404


async def test_get_chat_ordenado_asc(client: AsyncClient) -> None:
    """GET /chat devuelve los mensajes ordenados asc por creado_en."""
    sid = await _crear_sesion(client)
    await client.post(f"{_BASE}/sessions/{sid}/chat", json={"autor": "alumno", "texto": "1"})
    await client.post(f"{_BASE}/sessions/{sid}/chat", json={"autor": "proctor", "texto": "2"})
    await client.post(f"{_BASE}/sessions/{sid}/chat", json={"autor": "alumno", "texto": "3"})

    resp = await client.get(f"{_BASE}/sessions/{sid}/chat")
    assert resp.status_code == 200
    textos = [m["texto"] for m in resp.json()]
    assert textos == ["1", "2", "3"]


async def test_get_chat_filtro_desde(client: AsyncClient) -> None:
    """GET /chat?desde=<ts> devuelve solo mensajes posteriores (polling incremental)."""
    sid = await _crear_sesion(client)
    r1 = await client.post(
        f"{_BASE}/sessions/{sid}/chat", json={"autor": "alumno", "texto": "viejo"}
    )
    creado_1 = r1.json()["creado_en"]
    await client.post(
        f"{_BASE}/sessions/{sid}/chat", json={"autor": "proctor", "texto": "nuevo"}
    )

    resp = await client.get(f"{_BASE}/sessions/{sid}/chat", params={"desde": creado_1})
    assert resp.status_code == 200
    textos = [m["texto"] for m in resp.json()]
    assert textos == ["nuevo"]  # 'viejo' (== desde) queda excluido (creado_en > desde)


async def test_get_chat_sesion_inexistente_404(client: AsyncClient) -> None:
    """GET /chat de sesion inexistente → 404."""
    resp = await client.get(
        f"{_BASE}/sessions/00000000-0000-0000-0000-000000000000/chat"
    )
    assert resp.status_code == 404
