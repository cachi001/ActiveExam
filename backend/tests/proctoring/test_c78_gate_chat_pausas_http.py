"""El gate de chat/pausas por HTTP: apagarlos tiene que APAGARLOS (c-78).

La parte pura (que el snapshot los congele y quien manda) esta en
`test_c78_gate_chat_pausas.py`. Aca se prueba lo que le importa al usuario: que
el endpoint efectivamente rechace.

Antes de c-78 los dos interruptores eran SOLO visuales: `Examen.tsx` escondia el
recuadro y ninguno de los 7 endpoints de chat/pausas consultaba la config. Apagar
el chat no impedia nada — cualquier cliente seguia escribiendo.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"
# admin_sistema, no coordinador: c-79 acotó al coordinador a SU materia y estas
# sesiones son modo 'test' (sin comisión), así que la pertenencia no se puede
# resolver. El institucional es el rol correcto para ejercitar el gate.
_STAFF = auth_headers(["admin_sistema"], username="admin-gate", email="admin@uni.edu")


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post(f"{_BASE}/sessions", json={"modo": "test"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _fijar_snapshot(engine, session_id: str, **interruptores) -> None:
    """Escribe los interruptores en la foto de ESA sesion, que es de donde el gate
    lee (no de la config viva: el examen corre contra su snapshot)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        fila = await s.get(ProctoringSessionModel, session_id)
        foto = dict(fila.config_snapshot or {})
        foto.update(interruptores)
        await s.execute(
            update(ProctoringSessionModel)
            .where(ProctoringSessionModel.id == session_id)
            .values(config_snapshot=foto)
        )
        await s.commit()


async def test_con_el_chat_apagado_el_POST_de_chat_da_403(
    client: AsyncClient, activeexam_engine
) -> None:
    sid = await _crear_sesion(client)
    await _fijar_snapshot(activeexam_engine, sid, chat_habilitado=False)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "te veo"},
        headers=_STAFF,
    )

    assert resp.status_code == 403, resp.text
    assert "chat" in resp.json()["detail"].lower()


async def test_con_el_chat_prendido_el_POST_sigue_funcionando(
    client: AsyncClient, activeexam_engine
) -> None:
    """El gate no puede romper el camino normal."""
    sid = await _crear_sesion(client)
    await _fijar_snapshot(activeexam_engine, sid, chat_habilitado=True)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "te veo"},
        headers=_STAFF,
    )

    assert resp.status_code == 201, resp.text


async def test_con_las_pausas_apagadas_solicitar_da_403(
    client: AsyncClient, activeexam_engine
) -> None:
    sid = await _crear_sesion(client)
    await _fijar_snapshot(activeexam_engine, sid, pausas_habilitadas=False)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "bano"}
    )

    assert resp.status_code == 403, resp.text
    assert "pausa" in resp.json()["detail"].lower()


async def test_apagar_el_chat_no_apaga_las_pausas(
    client: AsyncClient, activeexam_engine
) -> None:
    """Consistencia: son dos interruptores independientes y uno no puede arrastrar
    al otro."""
    sid = await _crear_sesion(client)
    await _fijar_snapshot(
        activeexam_engine, sid, chat_habilitado=False, pausas_habilitadas=True
    )

    chat = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "x"},
        headers=_STAFF,
    )
    pausa = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "bano"}
    )

    assert chat.status_code == 403
    assert pausa.status_code == 201, pausa.text


async def test_un_subject_que_no_es_uuid_da_403_y_no_revienta_con_500(
    client: AsyncClient, activeexam_engine
) -> None:
    """Salio a la luz armando estos tests: `tiene_pertenencia_de_sesion` compara
    contra columnas UUID, y un subject malformado hacia reventar el cast de asyncpg
    con un 500 donde correspondia un 403. Ya habia pasado por otro camino (guarda
    `_es_uuid` de stats); este habia quedado sin cubrir."""
    sid = await _crear_sesion(client)
    await _fijar_snapshot(activeexam_engine, sid, chat_habilitado=True)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "hola"},
        headers=auth_headers(
            ["tutor"], username="no-soy-uuid", email="x@uni.edu"
        ),
    )

    assert resp.status_code != 500, resp.text
    assert resp.status_code == 403


async def test_manda_la_foto_de_la_sesion_no_la_config_viva(
    client: AsyncClient, activeexam_engine
) -> None:
    """LO IMPORTANTE del diseño (decisión del dueño): la config NO se refresca a
    mitad del examen — para eso existe el snapshot. Una sesión que arrancó con el
    chat PRENDIDO lo conserva aunque después se apague globalmente."""
    sid = await _crear_sesion(client)
    await _fijar_snapshot(activeexam_engine, sid, chat_habilitado=True)

    # (La config viva del entorno de test tiene el chat apagado por default.)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "sigo pudiendo"},
        headers=_STAFF,
    )

    assert resp.status_code == 201, resp.text
