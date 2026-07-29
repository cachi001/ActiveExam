"""Servicio de cálculo de nota académica (C-69, tarea 7.1-7.2).

L2.5: la nota deriva SÓLO de respuestas correctas server-side.
El score/flags de proctoring NO entran en este cálculo (regla dura #5).

D3: es_correcta vive en la DB server-side, NUNCA viaja al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import (
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)

# Escala por defecto si el examen no existe o no tiene nota_maxima configurada.
_NOTA_MAXIMA_DEFAULT = 10.0


@dataclass(frozen=True, slots=True)
class RespuestaAlumno:
    """Respuesta del alumno para una pregunta: la opción que eligió."""

    pregunta_id: str
    opcion_elegida_id: str


async def calcular_nota_academica(
    *,
    db: AsyncSession,
    examen_contenido_id: str,
    respuestas: list[RespuestaAlumno],
) -> float:
    """Calcula la nota académica (0..nota_maxima) de un alumno dado su examen.

    Fórmula (idéntica a Moodle): nota = (respuestas_correctas / total_preguntas) *
    nota_maxima, **con dos decimales** y ROUND_HALF_UP (0.5→1,
    6.5→7) — el mismo redondeo que Moodle aplica con "Posiciones decimales = 0".
    NO se redondea a entero: la nota se ESCALA después al `grademax` real del ítem
    destino en Moodle (ver `write_grade`), y redondear antes de escalar perdería
    precisión — un 3 sobre 10 llegaría como 30 sobre 100 en vez de 33,33. El
    aprobado/desaprobado se decide sobre ESTA nota (resultados_query:
    nota >= nota_aprobacion), como en Moodle.

    ``nota_maxima`` se lee server-side desde la config POR EXAMEN
    (examen_contenido.nota_maxima, migración 0032); default 10 si el examen no
    existe. Si el examen no existe, no tiene preguntas, o las respuestas están
    vacías → 0.

    Opción B (pool de preguntas): SOLO cuentan las preguntas seleccionadas por el
    docente (``seleccionada=True``) — tanto el total como las correctas. Una
    respuesta a una pregunta deseleccionada no suma ni al numerador ni al
    denominador.

    No recibe ni usa score/flags de proctoring — L2.5: el proctoring no altera
    la nota académica de forma automática.
    """
    # Contar total de preguntas SELECCIONADAS del examen (opción B)
    total_result = await db.execute(
        select(PreguntaExamenModel.id).where(
            PreguntaExamenModel.examen_id == examen_contenido_id,
            PreguntaExamenModel.seleccionada.is_(True),
        )
    )
    pregunta_ids = [r for r in total_result.scalars().all()]
    total_preguntas = len(pregunta_ids)

    if total_preguntas == 0 or not respuestas:
        return 0.0

    # Para cada respuesta del alumno, verificar server-side si es_correcta
    correctas = 0
    for resp in respuestas:
        # Solo verificar respuestas que correspondan a preguntas de ESTE examen
        if resp.pregunta_id not in pregunta_ids:
            continue
        result = await db.execute(
            select(OpcionRespuestaModel.es_correcta).where(
                OpcionRespuestaModel.id == resp.opcion_elegida_id,
                OpcionRespuestaModel.pregunta_id == resp.pregunta_id,
            )
        )
        es_correcta = result.scalar_one_or_none()
        if es_correcta is True:
            correctas += 1

    # nota_maxima server-side por examen (default 10 si el examen no existe).
    nota_maxima_row = await db.execute(
        select(ExamenContenidoModel.nota_maxima).where(
            ExamenContenidoModel.id == examen_contenido_id
        )
    )
    nota_maxima = nota_maxima_row.scalar_one_or_none()
    escala = Decimal(str(nota_maxima)) if nota_maxima is not None else Decimal(str(_NOTA_MAXIMA_DEFAULT))

    # DOS decimales, alineado con Moodle: la libreta formatea las notas con 2
    # decimales, asi que redondear a entero de este lado desalineaba las escalas —
    # 15/20 sobre 10 es 7,5 y se convertia en 8, medio punto regalado que Moodle
    # nunca pidio. La conversion a la escala del item destino la hace el cliente
    # (write_grade) leyendo el grademax real.
    #
    # ROUND_HALF_UP y Decimal a proposito: el round() de Python usa banker's
    # rounding (round(0.5) = 0), que en notas se lee como un error.
    nota = (Decimal(correctas) / Decimal(total_preguntas) * escala).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(nota)
