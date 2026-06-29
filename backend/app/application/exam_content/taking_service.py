"""Servicio de lectura de examen para rendición del alumno (C-69, D3).

La proyección de rendición excluye es_correcta de todas las opciones.
D3: el cliente es sensor no confiable; la opción correcta NUNCA viaja al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exam_content.entities import ExamenContenido
from app.domain.exam_content.ports import AbstractExamenContenidoRepository


@dataclass(frozen=True, slots=True)
class OpcionRendicion:
    """Opción de respuesta proyectada para la rendición (sin es_correcta — D3)."""

    id: str
    texto: str
    orden: int
    # D3: es_correcta AUSENTE — nunca viaja al cliente


@dataclass(frozen=True, slots=True)
class PreguntaRendicion:
    """Pregunta proyectada para la rendición del alumno."""

    id: str
    enunciado: str
    tipo: str
    orden: int
    opciones: tuple[OpcionRendicion, ...]


@dataclass(frozen=True, slots=True)
class ExamenRendicion:
    """Proyección del examen de contenido para la rendición (sin opciones correctas).

    Incluye la config POR EXAMEN que el front usa al rendir: timer
    (``tiempo_limite_min``), shuffle (``mezclar_preguntas``) y la escala de la nota
    (``nota_maxima``/``nota_aprobacion``) para mostrarla. D3: SIN es_correcta.
    """

    id: str
    titulo: str
    preguntas: tuple[PreguntaRendicion, ...]
    tiempo_limite_min: int | None = None
    mezclar_preguntas: bool = False
    nota_maxima: float = 10.0
    nota_aprobacion: float = 6.0


def proyectar_examen(examen: ExamenContenido) -> ExamenRendicion:
    """Proyecta un ExamenContenido a ExamenRendicion, excluyendo es_correcta (D3).

    El orden de preguntas y opciones es estable (por ``orden`` ascendente).

    Opción B (pool de preguntas): solo se proyectan las preguntas seleccionadas
    por el docente (``seleccionada=True``). Las del pool no seleccionadas NO viajan
    a la rendición del alumno.
    """
    preguntas = tuple(
        PreguntaRendicion(
            id=p.id or "",
            enunciado=p.enunciado,
            tipo=p.tipo,
            orden=p.orden,
            opciones=tuple(
                OpcionRendicion(
                    id=o.id or "",
                    texto=o.texto,
                    orden=o.orden,
                )
                for o in sorted(p.opciones, key=lambda x: x.orden)
            ),
        )
        for p in sorted(examen.preguntas, key=lambda x: x.orden)
        if p.seleccionada
    )
    return ExamenRendicion(
        id=examen.id or "",
        titulo=examen.titulo,
        preguntas=preguntas,
        tiempo_limite_min=examen.tiempo_limite_min,
        mezclar_preguntas=examen.mezclar_preguntas,
        nota_maxima=examen.nota_maxima,
        nota_aprobacion=examen.nota_aprobacion,
    )


class LecturaExamenService:
    """Servicio de lectura de examen para la rendición del alumno."""

    def __init__(self, repo: AbstractExamenContenidoRepository) -> None:
        self._repo = repo

    async def obtener_para_rendir(self, examen_id: str) -> ExamenRendicion | None:
        """Devuelve la proyección sin es_correcta, o None si el examen no existe."""
        examen = await self._repo.obtener(examen_id)
        if examen is None:
            return None
        return proyectar_examen(examen)
