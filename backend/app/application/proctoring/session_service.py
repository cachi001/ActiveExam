"""Servicio de aplicacion para sesiones de proctoring slim.

Orquesta la creacion, listado y detalle de sesiones. No depende de Keycloak,
Vault ni MinIO. La logica de scoring se delega a scoring.py para evitar
duplicacion con el repositorio.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.scoring import calcular_score
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.proctoring import (
    ProctoringRepository,
    SesionResumenData,
)


async def crear_sesion(
    db: AsyncSession,
    modo: str,
    exam_id: str | None = None,
    etiqueta: str | None = None,
) -> ProctoringSessionModel:
    """Crea una nueva sesion de proctoring slim."""
    repo = ProctoringRepository(db)
    return await repo.crear_sesion(modo=modo, exam_id=exam_id, etiqueta=etiqueta)


async def listar_sesiones(db: AsyncSession) -> list[SesionResumenData]:
    """Lista todas las sesiones con total_eventos, total_discrepancias y score."""
    repo = ProctoringRepository(db)
    return await repo.listar_sesiones()


async def detalle_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Obtiene el detalle completo de una sesion (con eventos y biometria)."""
    repo = ProctoringRepository(db)
    return await repo.obtener_sesion(session_id)


async def eliminar_sesion(db: AsyncSession, session_id: str) -> bool:
    """Elimina una sesion por ID. Devuelve True si existia, False si no."""
    repo = ProctoringRepository(db)
    return await repo.eliminar_sesion(session_id)
