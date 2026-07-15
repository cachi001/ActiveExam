"""Integración de la RESOLUCION (fase 2) contra slim DB real (c-71 slice 2).

Cubre migración 0039 (columnas resolucion_* en proctoring_session) + el
servicio de resolución + la persistencia del acto en el audit_log inmutable
(hash-chain + trigger), contra Postgres real (sin mocks de DB, regla #4).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.resolution_service import (
    CasoNoAbiertoError,
    ResolucionAlreadyMadeError,
    ReviewResolutionService,
)
from app.application.review.service import ReviewDecisionService
from app.domain.review.decision import DecisionResolucion, DecisionRevision
from app.infrastructure.persistence.models.audit_log import AuditLogModel

# Importar los modelos referenciados por FKs de proctoring_session para que el
# registry resuelva las tablas al configurar el mapper (test-infra).
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
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


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _crear_sesion(factory) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"c71-{_suf()}")
        s.add(sesion)
        await s.commit()
        return sesion.id


async def _dejar_caso_abierto(factory, session_id: str) -> None:
    async with factory() as s:
        svc = ReviewDecisionService(
            repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
        )
        await svc.decide(
            session_id,
            decision=DecisionRevision.CASO_ABIERTO,
            actor="revisor-1",
            observaciones="derivado",
        )
        await s.commit()


async def _cleanup(factory, session_id: str) -> None:
    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.id == session_id
            )
        )
        await s.commit()


def _resolution_svc(s: AsyncSession) -> ReviewResolutionService:
    return ReviewResolutionService(
        repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
    )


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_anular_persiste_columnas_y_audita_acto_distinguible() -> None:
    factory = _factory()
    sid = await _crear_sesion(factory)
    try:
        await _dejar_caso_abierto(factory, sid)
        async with factory() as s:
            result = await _resolution_svc(s).resolve(
                sid,
                resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
                actor="autoridad-1",
                motivo="copia confirmada",
                evidencia_ref="clip-7",
            )
            await s.commit()
        assert result.nota_anulada is True
        async with factory() as s:
            row = (
                await s.execute(
                    select(
                        ProctoringSessionModel.resolucion,
                        ProctoringSessionModel.resolucion_actor,
                        ProctoringSessionModel.resolucion_at,
                        ProctoringSessionModel.resolucion_motivo,
                        ProctoringSessionModel.decision,
                    ).where(ProctoringSessionModel.id == sid)
                )
            ).first()
            assert row is not None
            assert row[0] == "anulado_por_fraude"
            assert row[1] == "autoridad-1"
            assert row[2] is not None
            assert row[3] == "copia confirmada"
            assert row[4] == "caso_abierto"  # la fase 1 permanece intacta
            # El audit tiene DOS acciones distinguibles: la de revisar (caso_abierto)
            # y la de resolver (anulado_por_fraude) — RN-RV-06.
            acciones = {
                r[0]
                for r in (
                    await s.execute(
                        select(AuditLogModel.accion).where(
                            AuditLogModel.evidencia_id == sid
                        )
                    )
                ).all()
            }
            assert "review.decision.caso_abierto" in acciones
            assert "review.decision.anulado_por_fraude" in acciones
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_resolver_caso_no_abierto_da_conflicto_sin_cambiar_nota() -> None:
    factory = _factory()
    sid = await _crear_sesion(factory)
    try:
        # Revisión termina en sin_hallazgos (caso NO abierto)
        async with factory() as s:
            await ReviewDecisionService(
                repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
            ).decide(
                sid,
                decision=DecisionRevision.SIN_HALLAZGOS,
                actor="r1",
                observaciones="falso positivo",
            )
            await s.commit()
        async with factory() as s:
            with pytest.raises(CasoNoAbiertoError):
                await _resolution_svc(s).resolve(
                    sid,
                    resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
                    actor="a",
                    motivo="x",
                    evidencia_ref="clip",
                )
            await s.rollback()
        async with factory() as s:
            row = (
                await s.execute(
                    select(ProctoringSessionModel.resolucion).where(
                        ProctoringSessionModel.id == sid
                    )
                )
            ).first()
            assert row is not None and row[0] is None  # nota sin cambios
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_resolver_dos_veces_es_inmutable() -> None:
    factory = _factory()
    sid = await _crear_sesion(factory)
    try:
        await _dejar_caso_abierto(factory, sid)
        async with factory() as s:
            await _resolution_svc(s).resolve(
                sid,
                resolucion=DecisionResolucion.CASO_DESCARTADO,
                actor="a1",
                motivo="sin fraude",
                evidencia_ref=None,
            )
            await s.commit()
        async with factory() as s:
            with pytest.raises(ResolucionAlreadyMadeError):
                await _resolution_svc(s).resolve(
                    sid,
                    resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
                    actor="a-malicioso",
                    motivo="intento cambiar",
                    evidencia_ref="clip",
                )
            await s.commit()
        async with factory() as s:
            row = (
                await s.execute(
                    select(ProctoringSessionModel.resolucion).where(
                        ProctoringSessionModel.id == sid
                    )
                )
            ).first()
            assert row is not None and row[0] == "caso_descartado"
    finally:
        await _cleanup(factory, sid)
