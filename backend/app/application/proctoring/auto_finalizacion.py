"""C-72 §4 — Auto-finalización LAZY de sesiones vencidas (H-3).

Una sesión abandonada (el alumno cerró el navegador, se le colgó la máquina, o
simplemente no volvió) quedaba `finalizada_en = NULL` para siempre y NUNCA se
puntuaba: el alumno perdía todo lo que respondió. Esto la cierra de forma LAZY —
al TOCAR la sesión (reanudar / responder / consultar) se detecta que venció y se
finaliza, puntuándola con las respuestas ya persistidas.

LAZY, no barrido: NO se asume ninguna arquitectura de cola/worker (regla dura de
dominio #4 — eso lo decide C-03). El cierre ocurre en el request que toca la
sesión vencida, reusando EXACTAMENTE el mismo camino de finalización + write-back
que la finalización manual (mismo gate de revisión). Idempotente: si ya está
finalizada, no hace nada.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.moodle.grade_calculator import (
    RespuestaAlumno,
    calcular_nota_academica,
)
from app.application.moodle.writeback_service import MoodleWritebackService
from app.application.proctoring.enforcement import gracia_seg_default
from app.application.proctoring.finalizar_con_writeback import (
    finalizar_sesion_con_writeback,
)
from app.domain.exam_content.deadline import deadline_efectivo, vencido
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.moodle_writeback import RespuestaAlumnoModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


async def auto_finalizar_si_vencida(
    db: AsyncSession,
    sesion: ProctoringSessionModel,
    *,
    writeback_svc: MoodleWritebackService | None,
    ahora: datetime | None = None,
    gracia_seg: int | None = None,
) -> bool:
    """Cierra la sesión si venció y sigue activa; devuelve True si la cerró AHORA.

    Idempotente: si ``finalizada_en`` ya está seteado, o la sesión no tiene examen
    vinculado, o todavía no venció, no hace nada y devuelve False. Al cerrar, calcula
    la nota sobre las respuestas PERSISTIDAS (las que entraron en plazo) y usa el
    mismo ``finalizar_sesion_con_writeback`` que la finalización manual — mismo
    write-back y mismo gate de revisión (§4.4). ``ahora`` es hora del servidor
    (nunca del cliente, regla dura #6).
    """
    if sesion.finalizada_en is not None:
        return False
    if sesion.examen_contenido_id is None:
        return False

    config = (
        await db.execute(
            select(
                ExamenContenidoModel.tiempo_limite_min,
                ExamenContenidoModel.cierre,
            ).where(ExamenContenidoModel.id == sesion.examen_contenido_id)
        )
    ).one_or_none()
    if config is None:
        return False
    tiempo_limite_min, cierre = config
    if cierre is None:
        return False

    ahora = ahora or datetime.now(timezone.utc)
    if gracia_seg is None:
        gracia_seg = gracia_seg_default()
    deadline = deadline_efectivo(
        creada_en=sesion.creada_en, tiempo_limite_min=tiempo_limite_min, cierre=cierre
    )
    if not vencido(deadline=deadline, ahora=ahora, gracia_seg=gracia_seg):
        return False

    # Vencida y activa → puntuar con lo persistido en plazo y cerrar (mismo camino
    # que la manual). El alumno se lleva su trabajo en vez de perder todo.
    resp_rows = await db.execute(
        select(RespuestaAlumnoModel).where(
            RespuestaAlumnoModel.session_id == sesion.id
        )
    )
    respuestas = [
        RespuestaAlumno(pregunta_id=r.pregunta_id, opcion_elegida_id=r.opcion_elegida_id)
        for r in resp_rows.scalars().all()
    ]
    nota = await calcular_nota_academica(
        db=db,
        examen_contenido_id=sesion.examen_contenido_id,
        respuestas=respuestas,
        # c-78 E-07: el denominador es el set que le tocó a este intento.
        session_id=sesion.id,
    )
    await finalizar_sesion_con_writeback(
        db=db,
        session_id=sesion.id,
        writeback_svc=writeback_svc,
        alumno_idnumber=sesion.alumno_idnumber or "",
        alumno_email=sesion.alumno_email or "",
        nota=nota,
    )
    return True
