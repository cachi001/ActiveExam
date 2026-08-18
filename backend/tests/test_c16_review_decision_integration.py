"""Tests de integración del review.decide contra activeexam DB real — UN SOLO PASO
(colapsa c-16 + c-71 slice 2).

Cubre migración 0052 (columnas decision_motivo/decision_evidencia_ids en
proctoring_session, dropea resolucion_*) + servicio + inmutabilidad (RN-RV-07)
contra Postgres real (sin mocks de DB, regla dura #4).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.review.decision import DecisionSesion
from app.infrastructure.persistence.models.audit_log import AuditLogModel

# Importar los modelos referenciados por FKs de proctoring_session para que el
# registry de SQLAlchemy resuelva las tablas (examen_contenido, materia,
# comision) al configurar el mapper. Sin esto, importar ProctoringSessionModel
# de forma aislada lanza NoReferencedTableError (test-infra, no producto).
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.infrastructure.persistence.session_activeexam import (
    create_activeexam_engine,
    create_activeexam_session_factory,
)


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_activeexam_session_factory(create_activeexam_engine(url))


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
async def test_decide_aprobado_persiste_columnas_y_audita() -> None:
    factory = _factory()
    sesion_id = await _crear_sesion(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            result = await svc.decide(
                sesion_id,
                decision=DecisionSesion.APROBADO,
                actor="revisor-1",
                motivo="cero evidencia",
            )
            await s.commit()
        assert result.previous == DecisionSesion.PENDIENTE
        assert result.new == DecisionSesion.APROBADO
        assert result.nota_anulada is False
        # Verificar columnas persistidas
        async with factory() as s:
            row = (
                await s.execute(
                    select(
                        ProctoringSessionModel.decision,
                        ProctoringSessionModel.decision_actor,
                        ProctoringSessionModel.decision_at,
                        ProctoringSessionModel.decision_motivo,
                        ProctoringSessionModel.decision_evidencia_ids,
                    ).where(ProctoringSessionModel.id == sesion_id)
                )
            ).first()
            assert row is not None
            assert row[0] == "aprobado"
            assert row[1] == "revisor-1"
            assert row[2] is not None
            assert row[3] == "cero evidencia"
            assert row[4] is None
            # Audit log
            audit = await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == "review.decision.aprobado",
                    AuditLogModel.evidencia_id == sesion_id,
                )
            )
            assert len(audit.all()) == 1
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_decide_anulado_persiste_motivo_y_evidencia_estructurada() -> None:
    factory = _factory()
    sesion_id = await _crear_sesion(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            result = await svc.decide(
                sesion_id,
                decision=DecisionSesion.ANULADO,
                actor="revisor-1",
                motivo="copia detectada",
                evidencia_ids=["evt-a", "evt-b"],
            )
            await s.commit()
        assert result.nota_anulada is True
        async with factory() as s:
            row = (
                await s.execute(
                    select(
                        ProctoringSessionModel.decision,
                        ProctoringSessionModel.decision_motivo,
                        ProctoringSessionModel.decision_evidencia_ids,
                    ).where(ProctoringSessionModel.id == sesion_id)
                )
            ).first()
            assert row is not None
            assert row[0] == "anulado"
            assert row[1] == "copia detectada"
            assert row[2] == ["evt-a", "evt-b"]
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
                decision=DecisionSesion.ANULADO,
                actor="r1",
                motivo="fraude",
                evidencia_ids=["evt-1"],
            )
            await s.commit()
        # Segunda → DecisionAlreadyMadeError
        async with factory() as s:
            svc = _build_service(s)
            with pytest.raises(DecisionAlreadyMadeError):
                await svc.decide(
                    sesion_id,
                    decision=DecisionSesion.APROBADO,
                    actor="r-malicioso",
                    motivo="intento cambiar",
                )
            await s.commit()
        # Verificar: la decision en DB sigue siendo anulado + 2 entradas en audit
        async with factory() as s:
            row = (
                await s.execute(
                    select(ProctoringSessionModel.decision).where(
                        ProctoringSessionModel.id == sesion_id
                    )
                )
            ).first()
            assert row is not None and row[0] == "anulado"
            audit = await s.execute(
                select(AuditLogModel.accion).where(
                    AuditLogModel.evidencia_id == sesion_id
                )
            )
            acciones = [r[0] for r in audit.all()]
            assert acciones.count("review.decision.anulado") == 2  # inicial + rechazo
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_revertir_anulacion_es_append_only_contra_db_real() -> None:
    factory = _factory()
    sesion_id = await _crear_sesion(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            await svc.decide(
                sesion_id,
                decision=DecisionSesion.ANULADO,
                actor="autoridad-1",
                motivo="fraude confirmado",
                evidencia_ids=["evt-9"],
            )
            await s.commit()
        async with factory() as s:
            svc = _build_service(s)
            await svc.revertir_anulacion(
                sesion_id, actor="c18-apelacion", motivo="apelacion exitosa"
            )
            await s.commit()
        async with factory() as s:
            # La columna `decision` NO se muta (append-only): sigue 'anulado'.
            row = (
                await s.execute(
                    select(ProctoringSessionModel.decision).where(
                        ProctoringSessionModel.id == sesion_id
                    )
                )
            ).first()
            assert row is not None and row[0] == "anulado"
            acciones = {
                r[0]
                for r in (
                    await s.execute(
                        select(AuditLogModel.accion).where(
                            AuditLogModel.evidencia_id == sesion_id
                        )
                    )
                ).all()
            }
            assert "review.decision.anulado" in acciones
            assert "review.decision.nota_restituida" in acciones
    finally:
        await _cleanup(factory, sesion_id)
