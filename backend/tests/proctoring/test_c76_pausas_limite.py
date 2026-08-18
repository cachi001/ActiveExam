"""C-76 bloque 4 — límite configurable de pausas por sesión.

Umbral `pausas_max_por_sesion` (default 2) en Configuración del Sistema. Se
consume al APROBAR (no al solicitar, D5 design c-76): el alumno siempre puede
pedir; el límite lo aplica quien resuelve la aprobación.

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixture propia
(function-scoped) en vez del `activeexam_engine` compartido del conftest de
proctoring: en este entorno, fixtures async SESSION-scoped disparan
"RuntimeError: no current event loop" con la combinación pytest-asyncio 0.26 +
Windows (falla preexistente e independiente de este change — reproducible en
tests/proctoring/test_c72_pausa_timeout.py, que usa el mismo `db_session`
compartido). Mismo patrón self-contenido que
tests/test_c69_config_chat_pausas.py / tests/proctoring/test_c69_sesion_propiedad.py.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.proctoring import chat_pausa_service
from app.application.proctoring.chat_pausa_service import LimitePausasExcedido
from app.infrastructure.persistence.models.chat_pausa import (
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

pytestmark = pytest.mark.asyncio

_TABLAS = ("mensaje_chat", "pausa_autorizada", "proctoring_session")


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
        await conn.run_sync(MensajeChatModel.__table__.create, checkfirst=True)
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


async def _pedir_y_aprobar(db: AsyncSession, session_id: str, *, limite: int | None):
    pausa = await chat_pausa_service.solicitar_pausa(db, session_id, motivo="baño")
    return await chat_pausa_service.resolver_pausa(
        db,
        pausa.id,
        accion="aprobar",
        tutor_actor="tutor-1",
        limite_pausas=limite,
    )


# --- El alumno SIEMPRE puede solicitar, sin importar el límite -------------


async def test_alumno_siempre_puede_solicitar_pausa(db: AsyncSession) -> None:
    sid = await _sesion(db)
    # Ya hay 2 pausas aprobadas (limite=2, alcanzado)...
    await _pedir_y_aprobar(db, sid, limite=2)
    await _pedir_y_aprobar(db, sid, limite=2)
    # ...y aun asi el alumno puede solicitar una tercera (solicitar_pausa no
    # recibe ni aplica ningun limite).
    pausa3 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="agua")
    assert pausa3 is not None
    assert pausa3.estado == "solicitada"


# --- Aprobación bajo el límite: OK -------------------------------------------


async def test_aprobar_bajo_el_limite_ok(db: AsyncSession) -> None:
    sid = await _sesion(db)
    pausa = await chat_pausa_service.solicitar_pausa(db, sid, motivo="baño")
    resuelta = await chat_pausa_service.resolver_pausa(
        db, pausa.id, accion="aprobar", tutor_actor="tutor-1", limite_pausas=2
    )
    assert resuelta.estado == "aprobada"


# --- Aprobación rechazada por límite -----------------------------------------


async def test_aprobar_en_el_limite_rechaza(db: AsyncSession) -> None:
    sid = await _sesion(db)
    # Consume las 2 permitidas.
    await _pedir_y_aprobar(db, sid, limite=2)
    await _pedir_y_aprobar(db, sid, limite=2)
    # La tercera solicitud existe, pero aprobarla excede el limite=2.
    pausa3 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="agua")
    with pytest.raises(LimitePausasExcedido):
        await chat_pausa_service.resolver_pausa(
            db, pausa3.id, accion="aprobar", tutor_actor="tutor-1", limite_pausas=2
        )
    # La pausa rechazada por limite queda 'solicitada' (no se auto-resuelve;
    # el proctor/tutor debe rechazarla explicitamente — audit trail humano).
    pendiente = await db.get(PausaAutorizadaModel, pausa3.id)
    assert pendiente.estado == "solicitada"


# --- Triangulación: límite distinto (1) --------------------------------------


async def test_aprobar_con_limite_1(db: AsyncSession) -> None:
    sid = await _sesion(db)
    await _pedir_y_aprobar(db, sid, limite=1)
    pausa2 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="agua")
    with pytest.raises(LimitePausasExcedido):
        await chat_pausa_service.resolver_pausa(
            db, pausa2.id, accion="aprobar", tutor_actor="tutor-1", limite_pausas=1
        )


# --- Rechazadas NO cuentan para el límite (Q2 del design) -------------------


async def test_pausas_rechazadas_no_cuentan_para_el_limite(db: AsyncSession) -> None:
    sid = await _sesion(db)
    p1 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="x")
    await chat_pausa_service.resolver_pausa(
        db, p1.id, accion="rechazar", tutor_actor="tutor-1",
        motivo_rechazo="no corresponde",
    )
    p2 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="y")
    # Con limite=1: solo la rechazada existe, no cuenta -> se puede aprobar.
    resuelta = await chat_pausa_service.resolver_pausa(
        db, p2.id, accion="aprobar", tutor_actor="tutor-1", limite_pausas=1
    )
    assert resuelta.estado == "aprobada"


# --- Sin límite explícito (backward-compat: no rompe callers viejos) --------


async def test_sin_limite_explicito_no_restringe(db: AsyncSession) -> None:
    sid = await _sesion(db)
    await _pedir_y_aprobar(db, sid, limite=None)
    p2 = await chat_pausa_service.solicitar_pausa(db, sid, motivo="otra")
    resuelta = await chat_pausa_service.resolver_pausa(
        db, p2.id, accion="aprobar", tutor_actor="tutor-1", limite_pausas=None
    )
    assert resuelta.estado == "aprobada"
