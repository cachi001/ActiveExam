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


async def _resolver_target_examen(
    db: AsyncSession, examen_contenido_id: str | None
) -> tuple[int | None, int | None, str | None]:
    """Devuelve (moodle_courseid, moodle_cmid, moodle_component) del examen, o (None,)*3.

    D12 (parte B): el destino del write-back es POR EXAMEN. C-73: incluye el component
    ('mod_assign'|'mod_quiz'). Si la sesión no tiene examen vinculado o el examen no
    existe, devuelve (None, None, None) → fallback global.
    """
    if not examen_contenido_id:
        return None, None, None

    from sqlalchemy import select

    from app.infrastructure.persistence.models.exam_content import (
        ExamenContenidoModel,
    )

    row = await db.execute(
        select(
            ExamenContenidoModel.moodle_courseid,
            ExamenContenidoModel.moodle_cmid,
            ExamenContenidoModel.moodle_component,
        ).where(ExamenContenidoModel.id == examen_contenido_id)
    )
    target = row.one_or_none()
    if target is None:
        return None, None, None
    return target.moodle_courseid, target.moodle_cmid, target.moodle_component


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
        alumno_idnumber: username del alumno (para Moodle identity).
        alumno_email: email del alumno.
        nota: nota ya calculada (None = no se persiste nota).

    Returns:
        La sesión actualizada, o None si no existe.
    """
    sesion = await session_service.finalizar_sesion(db=db, session_id=session_id)

    if sesion is None:
        return None

    # C-72 sección 12: al cerrar la sesión (manual o auto), cancelar cualquier pedido
    # de pausa 'solicitada' sin resolver — no debe quedar colgado en el panel del
    # proctor. Idempotente (solo toca 'solicitada'). Paso normal del cierre.
    from app.application.proctoring import chat_pausa_service

    await chat_pausa_service.cancelar_solicitudes_de_sesion(db, session_id)

    # D12 (parte B): destino del write-back POR EXAMEN. Se resuelve desde el examen
    # vinculado a la sesión (examen_contenido_id). Si el examen no tiene destino
    # propio (NULL), se cae al global (iniciar_writeback/write_grade lo resuelven).
    moodle_courseid, moodle_cmid, moodle_component = await _resolver_target_examen(
        db, sesion.examen_contenido_id
    )

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
                    moodle_courseid=moodle_courseid,
                    moodle_cmid=moodle_cmid,
                    moodle_component=moodle_component,
                )
            else:
                await persistir_nota_pendiente(
                    db=db,
                    session_id=session_id,
                    nota=nota,
                    alumno_idnumber=alumno_idnumber,
                    alumno_email=alumno_email,
                    moodle_courseid=moodle_courseid,
                    moodle_cmid=moodle_cmid,
                    moodle_component=moodle_component,
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
