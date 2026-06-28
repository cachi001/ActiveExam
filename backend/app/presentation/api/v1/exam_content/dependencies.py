"""Dependencias del endpoint de importación Moodle (C-69)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.exam_content.import_service import ImportacionMoodleService
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)


async def get_import_service(request: Request) -> AsyncIterator[ImportacionMoodleService]:
    """Provee ImportacionMoodleService ligado a una sesión async por request."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        service = ImportacionMoodleService(repo)
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise
