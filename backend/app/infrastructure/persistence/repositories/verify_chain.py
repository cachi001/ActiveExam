"""Adaptadores SQL slim para c-18 verify-chain.

- SqlEventMaterialRepository: lee proctoring_event.screenshot_b64 + screenshot_sha256
- SqlChainVerificationAuditor: escribe al audit_log via AuditLogSqlRepository
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import AuditEntry
from app.domain.verify_chain.ports import (
    ChainVerificationAuditor,
    EventMaterialRepository,
)
from app.infrastructure.persistence.models.proctoring import ProctoringEventModel
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository


class SqlEventMaterialRepository(EventMaterialRepository):
    """Lee `screenshot_b64` + `screenshot_sha256` de proctoring_event."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_event_material(
        self, event_id: str
    ) -> tuple[str | None, str | None] | None:
        stmt = select(
            ProctoringEventModel.screenshot_b64,
            ProctoringEventModel.screenshot_sha256,
        ).where(ProctoringEventModel.id == event_id)
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return (row[0], row[1])


class SqlChainVerificationAuditor(ChainVerificationAuditor):
    """Escribe cada verify-chain al audit_log con propósito declarado."""

    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditLogSqlRepository(session)

    async def log_chain_verification(
        self, event_id: str, *, actor: str, status: str, proposito: str
    ) -> None:
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",  # trigger lo completa
                ip="",
                user_agent="",
                accion=f"verify_chain.{status}",
                evidencia_id=event_id,
                proposito=proposito,
                hash_prev="",  # trigger lo completa
            )
        )
