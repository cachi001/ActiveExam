"""Tests de integración del review.decide contra slim DB real (c-16).

Cubre migración 0013 (columnas decision_* en proctoring_session) + servicio +
inmutabilidad (RN-RV-07).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.review.decision import DecisionTerminal
from app.infrastructure.persistence.models.audit_log import AuditLogModel
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


async def _crear_sesion(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"c16-{_suf()}")
        s.add(sesion)
        await s.commit()
        return sesion.id


async def _cleanup(factory, session_id: str) -> None:
    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.id == session_id
            )
        )
        await s.commit()


def _build_service(s: AsyncSession) -> ReviewDecisionService:
    return ReviewDecisionService(
        repo=SqlSessionReviewRepository(s),
        auditor=SqlReviewAuditor(s),
    )


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_decide_persiste_columnas_y_audita() -> None:
    factory = _factory()
    sesion_id = await _crear_sesion(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            result = await svc.decide(
                sesion_id,
                decision=DecisionTerminal.DESCARTADA,
                actor="revisor-1",
                observaciones="cero evidencia",
            )
            await s.commit()
        assert result.previous == DecisionTerminal.PENDIENTE
        assert result.new == DecisionTerminal.DESCARTADA
        # Verificar columnas persistidas
        async with factory() as s:
            row = (
                await s.execute(
                    select(
                        ProctoringSessionModel.decision,
                        ProctoringSessionModel.decision_actor,
                        ProctoringSessionModel.decision_at,
                        ProctoringSessionModel.decision_observaciones,
                    ).where(ProctoringSessionModel.id == sesion_id)
                )
            ).first()
            assert row is not None
            assert row[0] == "descartada"
            assert row[1] == "revisor-1"
            assert row[2] is not None
            assert row[3] == "cero evidencia"
            # Audit log
            audit = await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == "review.decision.descartada",
                    AuditLogModel.evidencia_id == sesion_id,
                )
            )
            assert len(audit.all()) == 1
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_decide_inmutable_segundo_intento_falla_y_audita_rechazo() -> None:
    factory = _factory()
    sesion_id = await _crear_sesion(factory)
    try:
        # Primera decision (OK)
        async with factory() as s:
            svc = _build_service(s)
            await svc.decide(
                sesion_id,
                decision=DecisionTerminal.DERIVADA,
                actor="r1",
                observaciones=None,
            )
            await s.commit()
        # Segunda → DecisionAlreadyMadeError
        async with factory() as s:
            svc = _build_service(s)
            with pytest.raises(DecisionAlreadyMadeError):
                await svc.decide(
                    sesion_id,
                    decision=DecisionTerminal.DESCARTADA,
                    actor="r-malicioso",
                    observaciones="intento cambiar",
                )
            await s.commit()
        # Verificar: la decision en DB sigue siendo derivada + 2 entradas en audit
        async with factory() as s:
            row = (
                await s.execute(
                    select(ProctoringSessionModel.decision).where(
                        ProctoringSessionModel.id == sesion_id
                    )
                )
            ).first()
            assert row is not None and row[0] == "derivada"
            audit = await s.execute(
                select(AuditLogModel.accion).where(
                    AuditLogModel.evidencia_id == sesion_id
                )
            )
            acciones = {r[0] for r in audit.all()}
            assert "review.decision.derivada" in acciones  # ambas: la inicial Y el rechazo
    finally:
        await _cleanup(factory, sesion_id)
