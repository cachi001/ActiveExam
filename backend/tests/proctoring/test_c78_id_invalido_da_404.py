"""c-78 — Un id que no es UUID responde 404, no 500.

Encontrado el 26/8/2026 recorriendo producción: pedir cualquier recurso con un id
que no sea un UUID devolvía **500 Internal Server Error**. Verificado en
producción sobre ``/exam-content/{id}``, ``/exam-content/{id}/preguntas``,
``/exam-content/{id}/impacto-baja`` y ``/users/{id}``.

La causa no es de cada endpoint: es que Postgres rechaza el literal al comparar
contra una columna ``uuid`` (``invalid input syntax for type uuid``), asyncpg lo
eleva y sale por arriba como 500. Por eso el arreglo tampoco va endpoint por
endpoint — son decenas, y el que se agregue mañana volvería a fallar. Va un
manejador de excepción que traduce ESE error concreto a 404.

Es lo mismo que "no existe": un id malformado no puede corresponder a ninguna
fila. Devolver 500 hace pensar que se rompió el servidor cuando en realidad el
pedido era inválido, y ensucia las métricas de error con ruido que no lo es.

Requiere Postgres real (DATABASE_URL). Sin mocks (regla dura de código).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Ids que no son UUID. El primero es el caso que apareció de verdad: una ruta
# inexistente (`/banco/preguntas`) que terminó matcheando `/{examen_id}/preguntas`
# con examen_id="banco".
_IDS_MALOS = ["banco", "no-es-uuid", "123", "'; DROP TABLE examen_contenido; --"]


async def test_detalle_de_examen_con_id_invalido_da_404(client: AsyncClient) -> None:
    for malo in _IDS_MALOS:
        resp = await client.get(f"/api/v1/exam-content/{malo}")
        assert resp.status_code != 500, (
            f"id {malo!r} devolvió 500: el pedido es inválido, no el servidor"
        )
        assert resp.status_code in (404, 422), resp.status_code


async def test_sesion_con_id_invalido_da_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/proctoring/sessions/no-es-uuid")
    assert resp.status_code != 500
    assert resp.status_code in (403, 404, 422), resp.status_code


async def test_un_uuid_valido_pero_inexistente_sigue_dando_404(
    client: AsyncClient,
) -> None:
    """Triangulación: el arreglo no puede tapar el 404 legítimo de siempre."""
    resp = await client.get(
        "/api/v1/exam-content/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.status_code


async def test_un_id_valido_sigue_funcionando(client: AsyncClient) -> None:
    """Y no puede romper el camino feliz: crear y leer una sesión sigue igual."""
    creada = await client.post("/api/v1/proctoring/sessions", json={"modo": "test"})
    assert creada.status_code == 201, creada.text
    assert creada.json()["id"]
