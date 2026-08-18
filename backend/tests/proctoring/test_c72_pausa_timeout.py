"""C-72 sección 12 — Timeout del PEDIDO de pausa.

Una pausa 'solicitada' sin responder expira por antigüedad (sale de la cola del
proctor) y se cancela al finalizar la sesión. Distinto de `pausa_max_min` (que
limita la duración de una pausa YA aprobada). La expiración es acto del sistema:
no aprueba ni rechaza (L2.5).

DB real (DATABASE_URL). Sin mocks (regla dura #4). Usa el conftest de proctoring
(`db_session`, `activeexam_engine`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import chat_pausa_service
from app.application.proctoring.finalizar_con_writeback import (
    finalizar_sesion_con_writeback,
)
from app.infrastructure.persistence.models.chat_pausa import PausaAutorizadaModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _sesion(db: AsyncSession) -> str:
    s = ProctoringSessionModel(modo="examen")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s.id


async def _pausa(
    db: AsyncSession, sid: str, *, solicitada_en: datetime | None = None
) -> PausaAutorizadaModel:
    p = await chat_pausa_service.solicitar_pausa(db, sid, "necesito ir al baño")
    assert p is not None
    if solicitada_en is not None:
        p.solicitada_en = solicitada_en
        await db.commit()
        await db.refresh(p)
    return p


# 12.1 — pausa 'solicitada' más vieja que el umbral → 'expirada' y fuera de la cola
async def test_pausa_vieja_expira(db_session: AsyncSession):
    sid = await _sesion(db_session)
    p = await _pausa(db_session, sid, solicitada_en=_now() - timedelta(seconds=300))
    n = await chat_pausa_service.expirar_solicitudes_vencidas(db_session, timeout_seg=120)
    assert n >= 1
    await db_session.refresh(p)
    assert p.estado == "expirada"
    # y no aparece en la cola de pendientes
    pendientes = await chat_pausa_service.listar_pausas_pendientes(db_session)
    assert p.id not in {pa.id for pa, _ in pendientes}


# 12.2 — pausa dentro del umbral sigue pendiente
async def test_pausa_reciente_no_expira(db_session: AsyncSession):
    sid = await _sesion(db_session)
    p = await _pausa(db_session, sid, solicitada_en=_now() - timedelta(seconds=30))
    await chat_pausa_service.expirar_solicitudes_vencidas(db_session, timeout_seg=120)
    await db_session.refresh(p)
    assert p.estado == "solicitada"


# 12.5 — la expiración NO aprueba ni rechaza (no abre ventana, no setea inicio_en)
async def test_expiracion_no_otorga_pausa(db_session: AsyncSession):
    sid = await _sesion(db_session)
    p = await _pausa(db_session, sid, solicitada_en=_now() - timedelta(seconds=300))
    await chat_pausa_service.expirar_solicitudes_vencidas(db_session, timeout_seg=120)
    await db_session.refresh(p)
    assert p.estado == "expirada"
    assert p.inicio_en is None  # NO se abrió ventana de pausa


# 12.9 — doble expiración es idempotente: la 2da corrida no re-toca la ya expirada
async def test_doble_expiracion_idempotente(db_session: AsyncSession):
    sid = await _sesion(db_session)
    p = await _pausa(db_session, sid, solicitada_en=_now() - timedelta(seconds=300))
    await chat_pausa_service.expirar_solicitudes_vencidas(db_session, timeout_seg=120)
    await db_session.refresh(p)
    resuelta_1 = p.resuelta_en
    assert p.estado == "expirada"
    await chat_pausa_service.expirar_solicitudes_vencidas(db_session, timeout_seg=120)
    await db_session.refresh(p)
    # sigue expirada y NO se re-mutó (mismo resuelta_en: el WHERE solo toca 'solicitada')
    assert p.estado == "expirada"
    assert p.resuelta_en == resuelta_1


# 12.3 / 12.4 — al finalizar la sesión (manual o auto, mismo camino) se cancelan
# las pausas 'solicitada' pendientes
async def test_finalizar_cancela_pausas_pendientes(db_session: AsyncSession):
    sid = await _sesion(db_session)
    p = await _pausa(db_session, sid)  # reciente, aún pendiente
    await finalizar_sesion_con_writeback(
        db=db_session, session_id=sid, writeback_svc=None, nota=None
    )
    await db_session.refresh(p)
    assert p.estado == "expirada"  # cerrada la sesión, no queda colgada
