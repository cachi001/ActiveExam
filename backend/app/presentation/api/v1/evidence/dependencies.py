"""Dependencias del subsistema de evidencia (C-12): compone el servicio de custodia.

Arma el ``EvidenceCustodyService`` sobre una sesion async: repos de Evidencia,
Sesion (clave HMAC) y Audit log; storage WORM, cola (``MessageQueuePort``) y
backplane (fan-out del evento critico). El WORM, la cola y el publisher concretos
viven en ``app.state`` (cableados en deploy); sin ellos las dependencias devuelven
500 explicito (twelve-factor, sin default inseguro).
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.evidence.service import EvidenceCustodyService
from app.infrastructure.messaging.backplane import build_backplane
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    EvidenceSqlRepository,
    SessionSqlRepository,
)


def build_custody_service(
    request: Request, session: AsyncSession
) -> EvidenceCustodyService:
    """Compone el servicio de custodia (etapa 2) sobre una sesion async."""
    worm = getattr(request.app.state, "worm_storage", None)
    cola = getattr(request.app.state, "message_queue", None)
    if worm is None or cola is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subsistema de evidencia no inicializado (WORM/cola).",
        )

    settings = getattr(request.app.state, "settings", None)
    backend = getattr(settings, "messaging_backend", "postgres") if settings else "postgres"
    publisher = getattr(request.app.state, "backplane_publisher", None)
    if publisher is None:
        async def _noop(_canal: str, _evento: dict) -> None:
            return None

        publisher = _noop
    backplane = build_backplane(backend, publisher)

    return EvidenceCustodyService(
        evidencias=EvidenceSqlRepository(session),
        sesiones=SessionSqlRepository(session),
        audit=AuditLogSqlRepository(session),
        worm=worm,
        cola=cola,
        backplane=backplane,
    )
