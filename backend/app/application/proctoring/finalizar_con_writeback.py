"""Orquestador de finalización de sesión + persistencia de la nota (C-69, D8, D10).

D8: la nota se calcula server-side al finalizar la sesión.

Decisión de producto (admin-sync): al finalizar, la nota se CALCULA y PERSISTE con
estado 'pendiente', pero NO se auto-envía a Moodle. El envío a Moodle pasó a ser
MANUAL por el admin (endpoint POST /exam-content/{examen_id}/sincronizar-moodle).
Así el envío deja de depender de la disponibilidad de Moodle al finalizar y queda
bajo control humano (revisión previa de las notas).

La persistencia de la nota es fire-and-forget: si fallara, la finalización (la
operación crítica para el alumno) no se bloquea ni relanza.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import session_service
from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    persistir_nota_pendiente,
)
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
    """Finaliza la sesión y PERSISTE la nota como 'pendiente' (sin enviar a Moodle).

    El envío a Moodle es manual por el admin (decisión de producto). Acá solo se
    deja la nota lista para sincronizar. La persistencia no bloquea la finalización:
    cualquier excepción se captura para no propagar al endpoint.

    Args:
        db: sesión de DB.
        session_id: ID de la sesión a finalizar.
        writeback_svc: servicio de writeback (None = Moodle no configurado; la nota
            igual se persiste 'pendiente' vía persistir_nota_pendiente).
        alumno_idnumber: id_institucional del alumno (para Moodle identity).
        alumno_email: email del alumno.
        nota: nota ya calculada (None = no se persiste nota).

    Returns:
        La sesión actualizada, o None si no existe.
    """
    sesion = await session_service.finalizar_sesion(db=db, session_id=session_id)

    if sesion is None:
        return None

    # Persistir la nota como 'pendiente' SIN enviar a Moodle (envío manual del admin).
    if nota is not None:
        try:
            if writeback_svc is not None:
                await writeback_svc.iniciar_writeback(
                    db=db,
                    session_id=session_id,
                    nota=nota,
                    alumno_idnumber=alumno_idnumber,
                    alumno_email=alumno_email,
                )
            else:
                await persistir_nota_pendiente(
                    db=db,
                    session_id=session_id,
                    nota=nota,
                    alumno_idnumber=alumno_idnumber,
                    alumno_email=alumno_email,
                )
            # finalizar_sesion ya commiteó la sesión; el persist de la nota corre
            # después con solo flush, así que necesita su propio commit o se pierde.
            await db.commit()
        except Exception:
            # Nunca propagar — la finalización es la operación crítica para el alumno
            logger.exception(
                "Persistir nota pendiente falló al finalizar sesión %s — finaliza igual",
                session_id,
            )

    return sesion
