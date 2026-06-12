"""Servicio que decide una sesion con inmutabilidad (c-16 slim).

Regla dura RN-RV-07: la decision terminal es INMUTABLE — una vez seteada,
no se puede cambiar. Cualquier intento devuelve error con la decision actual.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.review.decision import (
    DecisionTerminal,
    ReviewDecisionResult,
    es_terminal,
)
from app.domain.review.ports import ReviewAuditor, SessionReviewRepository


class DecisionAlreadyMadeError(Exception):
    """Se intento cambiar una decision ya tomada (RN-RV-07: inmutable)."""

    def __init__(self, session_id: str, current: DecisionTerminal) -> None:
        super().__init__(
            f"Sesion {session_id!r} ya tiene decision terminal {current.value!r}: "
            "es inmutable (RN-RV-07)."
        )
        self.session_id = session_id
        self.current = current


_PURPOSE = (
    "review.decide: registro inmutable de decision terminal (RN-RV-07, L2.5)"
)


@dataclass
class ReviewDecisionService:
    repo: SessionReviewRepository
    auditor: ReviewAuditor

    async def decide(
        self,
        session_id: str,
        *,
        decision: DecisionTerminal,
        actor: str,
        observaciones: str | None,
    ) -> ReviewDecisionResult:
        """Persiste la decision si la sesion no tiene una terminal previa."""
        if not es_terminal(decision):
            raise ValueError(
                f"Decision {decision.value!r} no es terminal. "
                "Solo descartada/escalada/derivada son terminales."
            )

        record = await self.repo.get_decision(session_id)
        if record is None:
            raise ValueError(f"Sesion {session_id!r} no encontrada")

        if es_terminal(record.decision):
            # Auditamos el intento aunque rechazado (RN-RV-07 trazabilidad)
            await self.auditor.log_decision(
                session_id,
                actor=actor,
                decision=record.decision.value,
                proposito=(
                    "review.decide: intento de cambiar decision terminal — RECHAZADO"
                ),
            )
            raise DecisionAlreadyMadeError(session_id, record.decision)

        decision_at = await self.repo.persist_decision(
            session_id,
            decision=decision,
            actor=actor,
            observaciones=observaciones,
        )
        await self.auditor.log_decision(
            session_id,
            actor=actor,
            decision=decision.value,
            proposito=_PURPOSE,
        )

        return ReviewDecisionResult(
            session_id=session_id,
            previous=record.decision,
            new=decision,
            actor=actor,
            decision_at=decision_at,
        )
