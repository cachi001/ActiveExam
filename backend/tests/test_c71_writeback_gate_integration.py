"""Gate del write-back a Moodle por estado de revisión (c-71 slice 2, D15).

Contra DB real (sin mocks, regla #4): `listar_estados_sincronizables` — el único
punto donde una nota pasa a 'enviado' (sync manual del admin) — RETIENE las
sesiones flaggeadas/`caso_abierto`/`anulado_por_fraude` y LIBERA las resueltas
limpias o nunca flaggeadas.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.moodle.resultados_query import listar_estados_sincronizables
from app.application.review.resolution_service import ReviewResolutionService
from app.application.review.service import ReviewDecisionService
from app.domain.review.decision import DecisionResolucion, DecisionRevision
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
    EventoScoreConfigModel,
)
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)

UMBRAL = 40


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_slim_session_factory(create_slim_engine(url))


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _seed_config(factory) -> None:
    async with factory() as s:
        existing = await s.get(ConfiguracionSistemaModel, "global")
        if existing is None:
            s.add(
                ConfiguracionSistemaModel(id="global", umbral_cola_revision=UMBRAL)
            )
        else:
            existing.umbral_cola_revision = UMBRAL
        # peso alto para forzar flaggeada
        from sqlalchemy import select

        rows = await s.execute(
            select(EventoScoreConfigModel).where(
                EventoScoreConfigModel.tipo_evento == "rostro_ausente"
            )
        )
        if rows.scalars().first() is None:
            s.add(
                EventoScoreConfigModel(
                    tipo_evento="rostro_ausente",
                    severidad="alta",
                    peso=50,
                    activo=True,
                )
            )
        await s.commit()


async def _crear_examen(factory) -> str:
    async with factory() as s:
        ex = ExamenContenidoModel(titulo=f"c71-wb-{_suf()}")
        s.add(ex)
        await s.flush()
        eid = ex.id
        await s.commit()
        return eid


async def _crear_sesion(
    factory, examen_id: str, *, flaggeada: bool
) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen", examen_contenido_id=examen_id, etiqueta=f"wb-{_suf()}"
        )
        sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        sid = sesion.id
        if flaggeada:
            # 1 evento multiples_rostros (peso 50, seed) -> score 50 >= 40 -> flaggeada.
            s.add(
                ProctoringEventModel(
                    session_id=sid,
                    tipo="multiples_rostros",
                    severidad="alta",
                    ts_cliente=datetime.now(timezone.utc),
                )
            )
        s.add(
            MoodleWritebackEstadoModel(
                session_id=sid,
                alumno_idnumber=f"leg-{_suf()}",
                alumno_email=f"{_suf()}@u.edu",
                nota=7.0,
                estado="pendiente",
                intento=0,
            )
        )
        await s.commit()
        return sid


async def _decidir(factory, sid, decision) -> None:
    async with factory() as s:
        await ReviewDecisionService(
            repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
        ).decide(sid, decision=decision, actor="rev", observaciones="x")
        await s.commit()


async def _resolver(factory, sid, resolucion) -> None:
    await _decidir(factory, sid, DecisionRevision.CASO_ABIERTO)
    async with factory() as s:
        await ReviewResolutionService(
            repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
        ).resolve(
            sid,
            resolucion=resolucion,
            actor="autoridad",
            motivo="motivo",
            evidencia_ref="clip"
            if resolucion is DecisionResolucion.ANULADO_POR_FRAUDE
            else None,
        )
        await s.commit()


async def _sincronizables_ids(factory, examen_id: str) -> set[str]:
    async with factory() as s:
        filas = await listar_estados_sincronizables(db=s, examen_id=examen_id)
        return {f.session_id for f in filas}


async def _cleanup(factory, examen_id: str, sids: list[str]) -> None:
    async with factory() as s:
        for sid in sids:
            await s.execute(
                delete(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == sid
                )
            )
        await s.execute(
            delete(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
        )
        await s.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_flaggeada_retiene_sin_flag_envia() -> None:
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    flag = await _crear_sesion(factory, eid, flaggeada=True)
    limpia = await _crear_sesion(factory, eid, flaggeada=False)
    try:
        ids = await _sincronizables_ids(factory, eid)
        assert limpia in ids  # sin flag -> se envía
        assert flag not in ids  # flaggeada sin revisar -> hold
    finally:
        await _cleanup(factory, eid, [flag, limpia])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_caso_abierto_retiene_resolucion_limpia_libera() -> None:
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    abierta = await _crear_sesion(factory, eid, flaggeada=True)
    descartada = await _crear_sesion(factory, eid, flaggeada=True)
    try:
        await _decidir(factory, abierta, DecisionRevision.CASO_ABIERTO)
        await _resolver(factory, descartada, DecisionResolucion.CASO_DESCARTADO)
        ids = await _sincronizables_ids(factory, eid)
        assert abierta not in ids  # caso_abierto -> hold
        assert descartada in ids  # resuelta limpia -> release
    finally:
        await _cleanup(factory, eid, [abierta, descartada])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_anulado_por_fraude_nunca_se_envia() -> None:
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    anulada = await _crear_sesion(factory, eid, flaggeada=True)
    try:
        await _resolver(factory, anulada, DecisionResolucion.ANULADO_POR_FRAUDE)
        ids = await _sincronizables_ids(factory, eid)
        assert anulada not in ids  # anulado_por_fraude -> nunca se envía
    finally:
        await _cleanup(factory, eid, [anulada])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_revision_limpia_libera_un_hold_previo() -> None:
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    sid = await _crear_sesion(factory, eid, flaggeada=True)
    try:
        # Antes de revisar: flaggeada -> hold.
        assert sid not in await _sincronizables_ids(factory, eid)
        # Revisión limpia (sin_hallazgos) -> libera.
        await _decidir(factory, sid, DecisionRevision.SIN_HALLAZGOS)
        assert sid in await _sincronizables_ids(factory, eid)
    finally:
        await _cleanup(factory, eid, [sid])
