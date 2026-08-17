"""C-76 bloque 5 — screenshots del alumno durante la pausa.

D6: durante una ventana 'aprobada' el cliente sube capturas (evento
'captura_pausa', BASELINE — reusa el pipeline general de eventos, ya
re-hasheado/firmado server-side, regla dura #6). Al CERRAR la ventana
(finalizar_pausa), si no hubo ninguna captura, el sistema emite
'pausa_sin_captura' (BASELINE) como SEÑAL para revision humana — nunca un
veredicto (L2.5) ni algo que sume solo al score.

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixture propia
(function-scoped) — ver test_c76_pausas_limite.py para la justificación de no
usar el `db_session`/`activeexam_engine` compartido del conftest en este entorno.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.proctoring import chat_pausa_service
from app.domain.events.schema import TipoEvento
from app.infrastructure.persistence.models.chat_pausa import PausaAutorizadaModel
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)

pytestmark = pytest.mark.asyncio

_TABLAS = ("proctoring_event", "pausa_autorizada", "proctoring_session")


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no esta seteada; test de integracion (DB real).")

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(ProctoringSessionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringEventModel.__table__.create, checkfirst=True)
        await conn.run_sync(PausaAutorizadaModel.__table__.create, checkfirst=True)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _sesion(db: AsyncSession) -> str:
    s = ProctoringSessionModel(modo="examen")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s.id


async def _pausa_aprobada(db: AsyncSession, session_id: str) -> str:
    pausa = await chat_pausa_service.solicitar_pausa(db, session_id, motivo="baño")
    resuelta = await chat_pausa_service.resolver_pausa(
        db, pausa.id, accion="aprobar", tutor_actor="tutor-1"
    )
    return resuelta.id


async def _crear_captura_pausa(db: AsyncSession, session_id: str) -> None:
    """Simula lo que el pipeline general de eventos ya hace: persistir un evento
    'captura_pausa' re-hasheado (screenshot_sha256) para la sesion."""
    ev = ProctoringEventModel(
        session_id=session_id,
        tipo=TipoEvento.CAPTURA_PAUSA.value,
        severidad="baseline",
        ts_cliente=datetime.now(tz=timezone.utc),
        screenshot_sha256="a" * 64,
    )
    db.add(ev)
    await db.commit()


# --- Captura persistida y firmada -------------------------------------------


async def test_captura_pausa_persistida_y_firmada(db: AsyncSession) -> None:
    sid = await _sesion(db)
    await _crear_captura_pausa(db, sid)
    result = await db.execute(
        select(ProctoringEventModel).where(
            ProctoringEventModel.session_id == sid,
            ProctoringEventModel.tipo == TipoEvento.CAPTURA_PAUSA.value,
        )
    )
    eventos = result.scalars().all()
    assert len(eventos) == 1
    assert eventos[0].screenshot_sha256 == "a" * 64


# --- Ausencia registrada como señal, sin veredicto --------------------------


async def test_ausencia_de_captura_emite_senal_al_finalizar(db: AsyncSession) -> None:
    sid = await _sesion(db)
    pausa_id = await _pausa_aprobada(db, sid)
    # Sin ninguna captura durante la ventana.
    await chat_pausa_service.finalizar_pausa(db, pausa_id)

    result = await db.execute(
        select(ProctoringEventModel).where(
            ProctoringEventModel.session_id == sid,
            ProctoringEventModel.tipo == TipoEvento.PAUSA_SIN_CAPTURA.value,
        )
    )
    eventos = result.scalars().all()
    assert len(eventos) == 1
    # Severidad BASELINE: es señal, no veredicto (L2.5) — no auto-sanciona.
    assert eventos[0].severidad == "baseline"


async def test_con_captura_no_emite_senal_de_ausencia(db: AsyncSession) -> None:
    sid = await _sesion(db)
    pausa_id = await _pausa_aprobada(db, sid)
    await _crear_captura_pausa(db, sid)
    await chat_pausa_service.finalizar_pausa(db, pausa_id)

    result = await db.execute(
        select(ProctoringEventModel).where(
            ProctoringEventModel.session_id == sid,
            ProctoringEventModel.tipo == TipoEvento.PAUSA_SIN_CAPTURA.value,
        )
    )
    assert result.scalars().all() == []


# --- Score no afectado automáticamente --------------------------------------


async def test_score_no_incluye_eventos_de_pausa(db: AsyncSession) -> None:
    """'captura_pausa'/'pausa_sin_captura' son BASELINE (peso 0 por defecto,
    L2.5): incluirlos en el calculo de score no debe sumar puntos, sean o no
    excluidos ademas por la ventana de pausa (C-15 6.4, doble red)."""
    from app.application.proctoring.scoring import calcular_score

    sid = await _sesion(db)
    pausa_id = await _pausa_aprobada(db, sid)
    await chat_pausa_service.finalizar_pausa(db, pausa_id)

    eventos_result = await db.execute(
        select(ProctoringEventModel).where(ProctoringEventModel.session_id == sid)
    )
    eventos = eventos_result.scalars().all()
    assert len(eventos) == 1  # el pausa_sin_captura emitido
    assert eventos[0].severidad == "baseline"

    score = calcular_score(eventos)
    assert score == 0
