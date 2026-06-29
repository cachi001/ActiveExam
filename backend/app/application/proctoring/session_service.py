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
    examen_contenido_id: str | None = None,
    alumno_idnumber: str | None = None,
    alumno_email: str | None = None,
) -> ProctoringSessionModel:
    """Crea una nueva sesion de proctoring slim.

    ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
    importado de Moodle XML (NULLABLE). ``alumno_idnumber``/``alumno_email``
    persisten la identidad del alumno (C-69, enforcement de intentos).
    """
    repo = ProctoringRepository(db)
    return await repo.crear_sesion(
        modo=modo,
        exam_id=exam_id,
        etiqueta=etiqueta,
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
    )


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


async def finalizar_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Setea finalizada_en = now() si es NULL (idempotente). None si no existe."""
    repo = ProctoringRepository(db)
    return await repo.finalizar_sesion(session_id)


async def cerrar_forzado(
    db: AsyncSession,
    session_id: str,
    motivo: str,
    proctor_actor: str | None = None,
) -> ProctoringSessionModel | None:
    """Cierre forzado de la sesion por el proctor (operativo, NO disciplinario).

    Idempotente: si ya estaba cerrada de forma forzada, no muta el audit. None si
    la sesion no existe. Ver ProctoringRepository.cerrar_forzado."""
    repo = ProctoringRepository(db)
    return await repo.cerrar_forzado(session_id, motivo=motivo, proctor_actor=proctor_actor)


async def eliminar_sesion(db: AsyncSession, session_id: str) -> bool:
    """Elimina una sesion por ID. Devuelve True si existia, False si no."""
    repo = ProctoringRepository(db)
    return await repo.eliminar_sesion(session_id)
