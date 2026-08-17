"""Puertos del dominio review (modelo de un solo paso)."""

from __future__ import annotations

from typing import Protocol

from app.domain.review.decision import DecisionSesion, ReviewDecisionRecord


class SessionReviewRepository(Protocol):
    """Lee y persiste la decision en proctoring_session (columnas activeexam)."""

    async def get_decision(
        self, session_id: str
    ) -> ReviewDecisionRecord | None: ...

    async def persist_decision(
        self,
        session_id: str,
        *,
        decision: DecisionSesion,
        actor: str,
        motivo: str | None,
        evidencia_ids: list[str],
    ) -> str:
        """Persiste la decision atomicamente. Devuelve decision_at ISO 8601."""
        ...


class ReviewAuditor(Protocol):
    """Asienta cada decision al audit log con propopsito declarado."""

    async def log_decision(
        self,
        session_id: str,
        *,
        actor: str,
        decision: str,
        proposito: str,
    ) -> None: ...
