"""Servicio de cálculo de nota académica (C-69, tarea 7.1-7.2).

L2.5: la nota deriva SÓLO de respuestas correctas server-side.
El score/flags de proctoring NO entran en este cálculo (regla dura #5).

D3: es_correcta vive en la DB server-side, NUNCA viaja al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import (
    OpcionRespuestaModel,
    PreguntaExamenModel,
)


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
    """Calcula la nota académica (0..10) de un alumno dado su examen y respuestas.

    Fórmula: nota = (respuestas_correctas / total_preguntas) * 10.
    Si el examen no existe, no tiene preguntas, o las respuestas están vacías → 0.

    No recibe ni usa score/flags de proctoring — L2.5: el proctoring no altera
    la nota académica de forma automática.
    """
    # Contar total de preguntas del examen
    total_result = await db.execute(
        select(PreguntaExamenModel.id).where(
            PreguntaExamenModel.examen_id == examen_contenido_id
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

    return (correctas / total_preguntas) * 10.0
