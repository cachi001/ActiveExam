"""Puertos del dominio review (c-16 slim; resolucion c-71 slice 2)."""

from __future__ import annotations

from typing import Protocol

from app.domain.review.decision import (
    DecisionResolucion,
    DecisionTerminal,
    ResolutionRecord,
    ReviewDecisionRecord,
)


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

    async def get_resolution(
        self, session_id: str
    ) -> ResolutionRecord | None:
        """Lee el estado de RESOLUCION (fase 2) de la sesion, o None si no existe
        la sesion. Un record con ``resolucion=None`` = caso sin resolver."""
        ...

    async def persist_resolution(
        self,
        session_id: str,
        *,
        resolucion: DecisionResolucion,
        actor: str,
        motivo: str,
    ) -> str:
        """Persiste la resolucion atomicamente. Devuelve resolucion_at ISO 8601."""
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
