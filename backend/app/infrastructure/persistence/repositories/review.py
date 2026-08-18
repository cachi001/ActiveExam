"""Adaptador SQL para el modelo de decision de UN SOLO PASO (c-16 activeexam,
colapsado desde c-71 slice 2)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import AuditEntry
from app.domain.review.decision import DecisionSesion, ReviewDecisionRecord
from app.domain.review.ports import ReviewAuditor, SessionReviewRepository
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository


_PENDING_FALLBACK = DecisionSesion.PENDIENTE


def _parse_decision(value: str | None) -> DecisionSesion:
    if value is None:
        return _PENDING_FALLBACK
    try:
        return DecisionSesion(value)
    except ValueError:
        # Valor desconocido (p.ej. legado de un modelo anterior): sin datos
        # reales que migrar, cae conservador a pendiente.
        return _PENDING_FALLBACK


class SqlSessionReviewRepository(SessionReviewRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_decision(
        self, session_id: str
    ) -> ReviewDecisionRecord | None:
        result = await self._session.execute(
            select(
                ProctoringSessionModel.id,
                ProctoringSessionModel.decision,
                ProctoringSessionModel.decision_actor,
                ProctoringSessionModel.decision_at,
                ProctoringSessionModel.decision_motivo,
                ProctoringSessionModel.decision_evidencia_ids,
            ).where(ProctoringSessionModel.id == session_id)
        )
        row = result.first()
        if row is None:
            return None
        decision = _parse_decision(row[1])
        return ReviewDecisionRecord(
            session_id=str(row[0]),
            decision=decision,
            actor=row[2],
            decision_at=row[3].isoformat() if row[3] is not None else None,
            motivo=row[4],
            evidencia_ids=tuple(row[5] or ()),
        )

    async def persist_decision(
        self,
        session_id: str,
        *,
        decision: DecisionSesion,
        actor: str,
        motivo: str | None,
        evidencia_ids: list[str],
    ) -> str:
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(ProctoringSessionModel)
            .where(ProctoringSessionModel.id == session_id)
            .values(
                decision=decision.value,
                decision_actor=actor,
                decision_at=now,
                decision_motivo=motivo,
                decision_evidencia_ids=evidencia_ids or None,
            )
        )
        return now.isoformat()


class SqlReviewAuditor(ReviewAuditor):
    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditLogSqlRepository(session)
        self._session = session

    async def _actor_legible(self, actor: str) -> str:
        """Traduce el subject del JWT (un UUID) al email de la persona.

        El resto del sistema audita con el email y en la pantalla se leia
        "7a15e938-3fd9-48b3-aea4-eeb90ad09bbe" justo en las entradas mas
        sensibles — las decisiones sobre exámenes. Quien audita necesita saber
        QUIEN decidio, no su id interno.

        La traduccion se hace ACA y no aguas arriba a proposito: `decision_actor`
        en `proctoring_session` sigue guardando el subject, que es el identificador
        estable (el email puede cambiar). El audit muestra; la sesion identifica.

        Si el subject no resuelve a un usuario, se devuelve tal cual: una entrada
        de auditoria nunca se pierde por no poder embellecer un nombre.
        """
        from sqlalchemy import select

        from app.infrastructure.persistence.models.transactional import UsuarioModel

        try:
            email = (
                await self._session.execute(
                    select(UsuarioModel.email).where(UsuarioModel.id == actor)
                )
            ).scalar_one_or_none()
        except Exception:  # noqa: BLE001 — nunca romper la auditoria por esto
            return actor
        return email or actor

    async def log_decision(
        self,
        session_id: str,
        *,
        actor: str,
        decision: str,
        proposito: str,
    ) -> None:
        await self._audit.append(
            AuditEntry(
                actor=await self._actor_legible(actor),
                timestamp="",
                ip="",
                user_agent="",
                accion=f"review.decision.{decision}",
                evidencia_id=session_id,
                proposito=proposito,
                hash_prev="",
            )
        )
