"""Dependencias del cierre de sesion (C-13): compone el SessionFinalizationService."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.scoring.finalization import SessionFinalizationService
from app.infrastructure.persistence.repositories.event import EventSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    ExamSqlRepository,
    SessionSqlRepository,
)


def build_finalization_service(
    request: Request, session: AsyncSession
) -> SessionFinalizationService:
    """Compone el servicio de cierre sobre una sesion async."""
    cola = getattr(request.app.state, "message_queue", None)
    if cola is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cola no inicializada (message_queue).",
        )
    return SessionFinalizationService(
        sesiones=SessionSqlRepository(session),
        eventos=EventSqlRepository(session),
        examenes=ExamSqlRepository(session),
        cola=cola,
    )
