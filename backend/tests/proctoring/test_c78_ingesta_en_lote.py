"""c-78 §16.1f — Ingesta EN LOTE, para el drenaje del buffer al reconectar.

Por qué existe
--------------
Cuando a un alumno se le corta la conexión, lo que va pasando queda en el buffer
de IndexedDB y se reenvía al volver. Ese drenaje mandaba **un evento por
request**, esperando el ack de cada uno. Medido contra Render el 26/8/2026: una
caída de 30 s tardaba **35,6 s de media y hasta 1m01s** en drenarse (local eran
1,08 s — el plan free responde a 3 a 5 s por request y eso multiplica).

No se perdía evidencia (medido en cero), pero durante esos 35 s el alumno podía
cerrar la pestaña y llevarse lo que faltaba mandar.

Este endpoint acepta el lote entero en un solo request, **en orden**, y devuelve
un ack por evento en la misma posición.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de código).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/proctoring/sessions", json={"modo": "test"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _eventos_persistidos(client: AsyncClient, session_id: str) -> list[dict]:
    """Los eventos que quedaron en la sesión, leídos como los lee un revisor.

    El detalle de la sesión es un endpoint de SUPERVISIÓN: con el token del
    alumno responde 403. Y tiene que ser ADMIN, no coordinador: desde c-79 el
    coordinador está acotado a SUS materias, y una sesión `modo: 'test'` no tiene
    examen vinculado, así que la pertenencia no resuelve y devuelve
    `sesion_ajena`. Es la misma trampa que hizo fallar la primera medición de la
    caída de conexión contra Render.
    """
    resp = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}",
        headers=auth_headers(["admin_sistema"], subject="revisor-lote"),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["eventos"]


def _evento(n: int, tipo: str = "GAZE_DEVIATION") -> dict:
    return {
        "tipo": tipo,
        "severidad": "baja",
        "ts_cliente": f"2026-06-02T10:00:{n:02d}Z",
        "payload": {"n": n},
    }


async def test_un_lote_persiste_todos_los_eventos(client: AsyncClient) -> None:
    session_id = await _crear_sesion(client)

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": [_evento(n) for n in range(5)]},
    )

    assert resp.status_code == 201, resp.text
    acks = resp.json()["resultados"]
    assert len(acks) == 5
    assert all(a["evento_id"] for a in acks)

    # Y quedaron de verdad en la sesión.
    assert len(await _eventos_persistidos(client, session_id)) == 5


async def test_el_lote_respeta_el_orden_de_produccion(client: AsyncClient) -> None:
    """El orden es el del buffer, y el ack vuelve en la misma posición.

    Sin esto el cliente no puede casar cada ack con su evento para purgarlo.
    """
    session_id = await _crear_sesion(client)

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": [_evento(n) for n in range(4)]},
    )
    acks = resp.json()["resultados"]

    ids_persistidos = [e["id"] for e in await _eventos_persistidos(client, session_id)]
    ids_del_ack = [a["evento_id"] for a in acks]

    assert ids_del_ack == ids_persistidos, (
        "el ack no vuelve en el mismo orden en que se mandó el lote"
    )


async def test_un_lote_vacio_se_rechaza(client: AsyncClient) -> None:
    """Un lote sin eventos es un request al pedo: se rechaza en la validación."""
    session_id = await _crear_sesion(client)

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": []},
    )

    assert resp.status_code == 422, resp.text


async def test_un_lote_gigante_se_rechaza(client: AsyncClient) -> None:
    """Tope duro: sin él, un cliente puede mandar un lote que tumbe el request.

    El buffer del cliente drena de a tandas; el servidor no tiene por qué
    aceptar un lote sin límite.
    """
    session_id = await _crear_sesion(client)

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": [_evento(n) for n in range(201)]},
    )

    assert resp.status_code == 422, resp.text


async def test_el_lote_no_deja_entrar_en_la_sesion_de_otro(client: AsyncClient) -> None:
    """Misma guarda de IDOR que la ingesta de a uno (H1 del pentest).

    Si el lote no la tuviera, sería un agujero nuevo por la puerta de al lado.
    """
    session_id = await _crear_sesion(client)
    inexistente = "00000000-0000-0000-0000-000000000000"

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{inexistente}/events/lote",
        json={"eventos": [_evento(0)]},
    )

    assert resp.status_code in (403, 404), resp.text
    # La sesión propia sigue vacía: el rechazo no escribió nada en ningún lado.
    assert await _eventos_persistidos(client, session_id) == []


async def test_el_lote_devuelve_el_veredicto_igual_que_de_a_uno(
    client: AsyncClient,
) -> None:
    """El contrato del ack es el mismo: el cliente no distingue el camino."""
    session_id = await _crear_sesion(client)

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": [_evento(0, tipo="FACE_ABSENT")]},
    )

    ack = resp.json()["resultados"][0]
    assert ack["veredicto_reinferencia"] == "no_evaluado"
    assert ack["screenshot_sha256"] is None
    assert "face_count_servidor" in ack


async def test_un_lote_de_uno_equivale_a_la_ingesta_de_a_uno(
    client: AsyncClient,
) -> None:
    """Triangulación: el lote no es un camino paralelo con otras reglas."""
    session_id = await _crear_sesion(client)

    uno = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json=_evento(1, tipo="TAB_HIDDEN"),
    )
    lote = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events/lote",
        json={"eventos": [_evento(2, tipo="TAB_HIDDEN")]},
    )

    assert uno.status_code == 201 and lote.status_code == 201
    assert (
        uno.json()["veredicto_reinferencia"]
        == lote.json()["resultados"][0]["veredicto_reinferencia"]
    )

    assert len(await _eventos_persistidos(client, session_id)) == 2
