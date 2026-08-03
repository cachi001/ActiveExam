"""Proyección del veredicto de anulación en MiNota (c-71 slice 2, D11b/D12,
modelo de un solo paso).

El alumno ve el veredicto por PULL en GET /mis-notas. Verifica contra DB real
(sin mocks, regla #4) que:
- decision `anulado` (sin restitución) → nota_anulada + informe_disponible + veredicto;
- decision `aprobado` / sin decisión → nota NO anulada, informe NO disponible (minimización);
- un acto compensatorio `nota_restituida` posterior deriva el estado a NO anulada (D10b).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.moodle.resultados_query import listar_mis_notas
from app.application.review.service import ReviewDecisionService
from app.domain.review.decision import DecisionSesion
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_slim_session_factory(create_slim_engine(url))


def _idn() -> str:
    return f"c71-{uuid.uuid4().hex[:8]}"


async def _sesion_finalizada_con_nota(factory, idnumber: str, email: str) -> str:
    from datetime import datetime, timezone

    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"c71-{_idn()}")
        sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        sid = sesion.id
        s.add(
            MoodleWritebackEstadoModel(
                session_id=sid,
                alumno_idnumber=idnumber,
                alumno_email=email,
                nota=7.0,
                estado="pendiente",
                intento=0,
            )
        )
        await s.commit()
        return sid


async def _decidir(factory, sid: str, decision: DecisionSesion, *, evidencia_ids=None) -> None:
    async with factory() as s:
        await ReviewDecisionService(
            repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
        ).decide(
            sid,
            decision=decision,
            actor="revisor-1",
            motivo="motivo de la decision",
            evidencia_ids=evidencia_ids or [],
        )
        await s.commit()


async def _cleanup(factory, sid: str) -> None:
    async with factory() as s:
        await s.execute(
            delete(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == sid
            )
        )
        await s.execute(
            delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sid)
        )
        await s.commit()


async def _get_minota(factory, idnumber: str, email: str, sid: str):
    async with factory() as s:
        items, _ = await listar_mis_notas(
            db=s, alumno_idnumber=idnumber, alumno_email=email, moodle_configurado=True
        )
    return next((i for i in items if i.session_id == sid), None)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_anulado_proyecta_veredicto_e_informe() -> None:
    factory = _factory()
    idn, email = _idn(), f"{_idn()}@u.edu"
    sid = await _sesion_finalizada_con_nota(factory, idn, email)
    try:
        await _decidir(factory, sid, DecisionSesion.ANULADO, evidencia_ids=["evt-1"])
        mn = await _get_minota(factory, idn, email, sid)
        assert mn is not None
        assert mn.nota_anulada is True
        assert mn.veredicto == "anulado"
        assert mn.informe_disponible is True
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_aprobado_no_expone_informe_minimizacion() -> None:
    factory = _factory()
    idn, email = _idn(), f"{_idn()}@u.edu"
    sid = await _sesion_finalizada_con_nota(factory, idn, email)
    try:
        await _decidir(factory, sid, DecisionSesion.APROBADO)
        mn = await _get_minota(factory, idn, email, sid)
        assert mn is not None
        assert mn.nota_anulada is False
        assert mn.veredicto is None
        assert mn.informe_disponible is False
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sin_decision_no_expone_informe() -> None:
    factory = _factory()
    idn, email = _idn(), f"{_idn()}@u.edu"
    sid = await _sesion_finalizada_con_nota(factory, idn, email)
    try:
        mn = await _get_minota(factory, idn, email, sid)
        assert mn is not None
        assert mn.nota_anulada is False
        assert mn.informe_disponible is False
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_restitucion_posterior_deriva_a_no_anulada() -> None:
    factory = _factory()
    idn, email = _idn(), f"{_idn()}@u.edu"
    sid = await _sesion_finalizada_con_nota(factory, idn, email)
    try:
        await _decidir(factory, sid, DecisionSesion.ANULADO, evidencia_ids=["evt-1"])
        # Acto compensatorio append-only (hook c-18): restituye la nota.
        async with factory() as s:
            await ReviewDecisionService(
                repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
            ).revertir_anulacion(sid, actor="c18", motivo="apelacion exitosa")
            await s.commit()
        mn = await _get_minota(factory, idn, email, sid)
        assert mn is not None
        # La columna `decision` sigue 'anulado' (append-only, no UPDATE) pero el
        # estado DERIVADO del último acto es: NO anulada.
        assert mn.nota_anulada is False
        assert mn.informe_disponible is False
    finally:
        await _cleanup(factory, sid)
