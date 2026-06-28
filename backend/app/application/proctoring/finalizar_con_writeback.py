"""Orquestador de finalización de sesión + disparo de write-back (C-69, D8, D10).

D8: el write-back se origina server-side al finalizar la sesión.
D10: la finalización NO se bloquea por Moodle — es fire-and-forget.
Si Moodle no responde, la sesión finaliza igual y la nota queda en 'fallido'.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import session_service
from app.application.moodle.writeback_service import MoodleWritebackService
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

logger = logging.getLogger(__name__)


async def finalizar_sesion_con_writeback(
    *,
    db: AsyncSession,
    session_id: str,
    writeback_svc: MoodleWritebackService | None,
    alumno_idnumber: str = "",
    alumno_email: str = "",
    nota: float | None = None,
) -> ProctoringSessionModel | None:
    """Finaliza la sesión y dispara el write-back sin bloquear.

    Si el write-back falla o Moodle no responde, la sesión finaliza igual.
    El write-back se ejecuta en el mismo hilo pero las excepciones se capturan
    para no propagar hacia el finalizar endpoint.

    Args:
        db: sesión de DB.
        session_id: ID de la sesión a finalizar.
        writeback_svc: servicio de writeback (None = write-back deshabilitado).
        alumno_idnumber: id_institucional del alumno (para Moodle identity).
        alumno_email: email del alumno.
        nota: nota ya calculada (None = writeback omitido sin nota).

    Returns:
        La sesión actualizada, o None si no existe.
    """
    sesion = await session_service.finalizar_sesion(db=db, session_id=session_id)

    if sesion is None:
        return None

    # Disparar write-back sin bloquear la respuesta
    if writeback_svc is not None and nota is not None:
        try:
            await _ejecutar_writeback_en_background(
                writeback_svc=writeback_svc,
                db=db,
                session_id=session_id,
                nota=nota,
                alumno_idnumber=alumno_idnumber,
                alumno_email=alumno_email,
            )
        except Exception:
            # Nunca propagar — la finalización es la operación crítica
            logger.exception(
                "Write-back falló al finalizar sesión %s — la sesión finaliza igual",
                session_id,
            )

    return sesion


async def _ejecutar_writeback_en_background(
    *,
    writeback_svc: MoodleWritebackService,
    db: AsyncSession,
    session_id: str,
    nota: float,
    alumno_idnumber: str,
    alumno_email: str,
) -> None:
    """Ejecuta el write-back. Las excepciones se dejan subir para que el caller las capture."""
    await writeback_svc.ejecutar_writeback(
        db=db,
        session_id=session_id,
        nota=nota,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
    )
