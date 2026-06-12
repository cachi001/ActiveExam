"""Puertos del dominio review (c-16 slim)."""

from __future__ import annotations

from typing import Protocol

from app.domain.review.decision import DecisionTerminal, ReviewDecisionRecord


class SessionReviewRepository(Protocol):
    """Lee y persiste la decision en proctoring_session (4 columnas slim)."""

    async def get_decision(
        self, session_id: str
    ) -> ReviewDecisionRecord | None: ...

    async def persist_decision(
        self,
        session_id: str,
        *,
        decision: DecisionTerminal,
        actor: str,
        observaciones: str | None,
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
