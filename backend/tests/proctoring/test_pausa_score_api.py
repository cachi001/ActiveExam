"""Test de integracion — contextualizacion del score en el detalle del proctor (C-15 6.4.2).

Postgres real. Verifica que GET /sessions/{id} marca en_pausa_autorizada por evento
y EXCLUYE del score los eventos producidos durante una pausa aprobada (L2.5: el
evento NO se borra; queda en la lista con el badge).

Para que los eventos sumen al score se siembra una fila en ``evento_score_config``
(pesos VIVOS por tipo) — la severidad del endpoint de eventos usa el catalogo
``bajo/medio/alto/critico``, que NO coincide con las claves del fallback por
severidad del scoring (``baja/media/alta/critica``); por eso el score realista en
el detalle viene de la config por tipo, no del fallback.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"
_PESO_GAZE = 50  # peso vivo sembrado para GAZE_DEVIATION

# GET /sessions/{id} (detalle) y PATCH /pausas/{id} (aprobar) son del proctor; el
# ``client`` por defecto va como estudiante. Se mandan con Bearer de rol proctor.
_PROCTOR = auth_headers(["coordinador"])  # c-76: rol proctor eliminado -> coordinador supervisa


@pytest_asyncio.fixture
async def score_config(activeexam_engine):
    """Crea evento_score_config y siembra GAZE_DEVIATION=50 (peso vivo por tipo)."""
    async with activeexam_engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS evento_score_config ("
                "tipo_evento text PRIMARY KEY, severidad text NOT NULL, "
                "peso integer NOT NULL, descripcion text, "
                "activo boolean NOT NULL DEFAULT true)"
            )
        )
        await conn.execute(text("TRUNCATE evento_score_config"))
        await conn.execute(
            text(
                "INSERT INTO evento_score_config (tipo_evento, severidad, peso, activo) "
                "VALUES ('GAZE_DEVIATION', 'alta', :peso, true)"
            ),
            {"peso": _PESO_GAZE},
        )
    yield
    async with activeexam_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS evento_score_config CASCADE"))


async def _evento(client: AsyncClient, sid: str) -> None:
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "alto",
            "ts_cliente": "2026-06-22T10:00:00Z",
            "face_count_cliente": 1,
        },
    )
    assert resp.status_code in (200, 201)


async def test_detalle_evento_fuera_de_pausa_cuenta_en_score(
    client: AsyncClient, score_config
) -> None:
    """Sin pausa: el evento cuenta en el score y en_pausa_autorizada=False."""
    sid = (await client.post(f"{_BASE}/sessions", json={"modo": "test"})).json()["id"]
    await _evento(client, sid)

    resp = await client.get(f"{_BASE}/sessions/{sid}", headers=_PROCTOR)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == _PESO_GAZE
    assert len(data["eventos"]) == 1
    assert data["eventos"][0]["en_pausa_autorizada"] is False


async def test_detalle_evento_en_pausa_excluido_del_score(
    client: AsyncClient, score_config
) -> None:
    """Con pausa aprobada activa: el evento se marca y se EXCLUYE del score, pero sigue en la lista."""
    sid = (await client.post(f"{_BASE}/sessions", json={"modo": "test"})).json()["id"]

    # Aprobar una pausa -> abre ventana (inicio_en = now, fin_en = NULL = activa)
    pid = (
        await client.post(f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "bano"})
    ).json()["id"]
    await client.patch(
        f"{_BASE}/pausas/{pid}",
        json={"accion": "aprobar", "tutor_actor": "doc"},
        headers=_PROCTOR,
    )

    # Evento DURANTE la pausa (ts_backend = now, dentro de la ventana activa)
    await _evento(client, sid)

    resp = await client.get(f"{_BASE}/sessions/{sid}", headers=_PROCTOR)
    assert resp.status_code == 200
    data = resp.json()
    # El evento sigue en la lista (no se borra — L2.5) con el badge
    assert len(data["eventos"]) == 1
    assert data["eventos"][0]["en_pausa_autorizada"] is True
    # Score excluye el evento en pausa -> 0
    assert data["score"] == 0


async def test_detalle_mezcla_dentro_y_fuera_de_pausa(
    client: AsyncClient, score_config
) -> None:
    """Un evento en pausa (excluido) + uno fuera (cuenta): score = solo el de afuera."""
    sid = (await client.post(f"{_BASE}/sessions", json={"modo": "test"})).json()["id"]

    # Evento ANTES de la pausa -> cuenta
    await _evento(client, sid)  # fuera, suma 50

    # Aprobar una pausa: abre ventana (inicio_en = now)
    pid = (
        await client.post(f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "x"})
    ).json()["id"]
    await client.patch(
        f"{_BASE}/pausas/{pid}",
        json={"accion": "aprobar", "tutor_actor": "doc"},
        headers=_PROCTOR,
    )
    # Evento DURANTE la ventana abierta -> excluido
    await _evento(client, sid)
    await client.patch(f"{_BASE}/pausas/{pid}/finalizar")

    resp = await client.get(f"{_BASE}/sessions/{sid}", headers=_PROCTOR)
    assert resp.status_code == 200
    data = resp.json()
    badges = [e["en_pausa_autorizada"] for e in data["eventos"]]
    # Exactamente un evento marcado en pausa, uno fuera
    assert badges.count(True) == 1
    assert badges.count(False) == 1
    # Score solo cuenta el evento fuera de pausa
    assert data["score"] == _PESO_GAZE
