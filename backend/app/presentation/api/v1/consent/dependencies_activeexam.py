"""Dependencias del consentimiento para el modulo activeexam (C-63).

En el modulo activeexam (Railway) la tabla ``consentimiento`` no existe, asi que se
usa ``NoOpConsentRepository`` en lugar de ``ConsentSqlRepository``. El resto
(audit log, alternative requests) es igual que en el full.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.consent.service import ConsentService
from app.infrastructure.persistence.repositories.alternative_request import (
    AlternativeRequestSqlRepository,
)
from app.infrastructure.persistence.repositories.audit_log_activeexam import (
    InMemoryAuditLogRepository,
)
from app.infrastructure.persistence.repositories.consent_activeexam import (
    NoOpConsentRepository,
)
from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage


class _NoOpQueue(MessageQueuePort):
    """Cola no-operativa para el modulo activeexam (sin Postgres-como-cola aun)."""

    async def enqueue(self, topic: str, payload: dict) -> str:
        # En activeexam no hay cola — retornar un id simulado.
        # Cuando C-03 decida la arquitectura, esto se reemplaza por el adaptador real.
        import uuid
        return str(uuid.uuid4())

    async def dequeue(self, topic: str) -> QueuedMessage | None:
        return None

    async def ack(self, message_id: str) -> None:
        return None

    async def health_check(self) -> bool:
        return True


async def get_consent_service_activeexam(request: Request) -> AsyncIterator[ConsentService]:
    """Provee el ConsentService para el modulo activeexam.

    Usa NoOpConsentRepository (tabla consentimiento no existe en activeexam) y
    AlternativeRequestSqlRepository para el flujo de via alternativa (C-63).
    """
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Consentimiento activeexam no inicializado (persistencia no disponible).",
        )
    async with factory() as session:
        service = ConsentService(
            consents=NoOpConsentRepository(),
            audit_log=InMemoryAuditLogRepository(),
            queue=_NoOpQueue(),
            alternative_requests=AlternativeRequestSqlRepository(session),
        )
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise
