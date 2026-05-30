"""Dependencias de la API de examenes: construye el caso de uso por request (C-07).

Abre una sesion async (factory cableada en ``app.state.session_factory``), arma los
repositorios SQLAlchemy (adaptadores de C-05) y el ``ExamConfigService``, y hace
commit/rollback al cerrar. El presign se toma de ``app.state.presign_service``.

Si el ``session_factory`` no esta cableado (entorno sin DB), la dependencia falla
con 500 explicito en vez de fingir. Los tests inyectan un override de la
dependencia con repositorios en memoria.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.exam_config.service import ExamConfigService
from app.infrastructure.persistence.repositories.transactional import (
    AssignmentSqlRepository,
    ExamSqlRepository,
)
from app.infrastructure.storage.presign import PresignService, StoragePresignService


async def get_exam_service(request: Request) -> AsyncIterator[ExamConfigService]:
    """Provee el ``ExamConfigService`` ligado a una sesion async por request."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    async with factory() as session:
        service = ExamConfigService(
            ExamSqlRepository(session), AssignmentSqlRepository(session)
        )
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_presign_service(request: Request) -> PresignService:
    """Provee el servicio de presign (cableado en app.state o construido de config)."""
    svc = getattr(request.app.state, "presign_service", None)
    if svc is not None:
        return svc
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage no inicializado (presign).",
        )
    return StoragePresignService(
        endpoint=settings.storage_endpoint, bucket=settings.storage_bucket_evidence
    )
