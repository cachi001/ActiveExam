"""Servicio de lectura de examen para rendición del alumno (C-69, D3).

La proyección de rendición excluye es_correcta de todas las opciones.
D3: el cliente es sensor no confiable; la opción correcta NUNCA viaja al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.exam_content.errors import MateriaInactivaError
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

    def __init__(
        self,
        repo: AbstractExamenContenidoRepository,
        comision_repo=None,
        materia_repo=None,
    ) -> None:
        self._repo = repo
        # Opcionales: si se proveen, se aplica el freeze de materia desactivada
        # (C-72 §17). None → sin chequeo (compat con callers/tests que solo leen).
        self._comision_repo = comision_repo
        self._materia_repo = materia_repo

    async def obtener_para_rendir(self, examen_id: str) -> ExamenRendicion | None:
        """Devuelve la proyección sin es_correcta, o None si el examen no existe.

        Freeze (C-72 §17): si el examen pertenece a una comisión de una materia
        DESACTIVADA, eleva ``MateriaInactivaError`` (no se puede iniciar la rendición).
        """
        examen = await self._repo.obtener(examen_id)
        if examen is None:
            return None
        await self._verificar_materia_activa(examen)
        return proyectar_examen(examen)

    async def _verificar_materia_activa(self, examen: ExamenContenido) -> None:
        # Sin repos de contexto no hay chequeo; un examen sin comisión (D11) tampoco
        # tiene materia que congelar.
        if self._comision_repo is None or self._materia_repo is None:
            return
        if not examen.comision_id:
            return
        comision = await self._comision_repo.obtener(examen.comision_id)
        if comision is None:
            return
        materia = await self._materia_repo.obtener(comision.materia_id)
        if materia is not None and not materia.activa:
            raise MateriaInactivaError(
                f"La materia {materia.nombre!r} está desactivada: no se puede "
                "iniciar la rendición de sus exámenes."
            )
