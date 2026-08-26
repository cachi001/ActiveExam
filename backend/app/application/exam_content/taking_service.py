"""Servicio de lectura de examen para rendición del alumno (C-69, D3).

La proyección de rendición excluye es_correcta de todas las opciones.
D3: el cliente es sensor no confiable; la opción correcta NUNCA viaja al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.exam_content.errors import (
    ComisionInactivaError,
    MateriaInactivaError,
)
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
class BlankRendicion:
    """Hueco cloze proyectado para la rendición (sin la respuesta correcta — D3)."""

    id: str
    orden: int
    tipo: str
    texto_antes: str
    texto_despues: str
    opciones: tuple[OpcionRendicion, ...]


@dataclass(frozen=True, slots=True)
class PreguntaRendicion:
    """Pregunta proyectada para la rendición del alumno."""

    id: str
    enunciado: str
    tipo: str
    orden: int
    opciones: tuple[OpcionRendicion, ...]
    # Solo poblado en preguntas cloze; el front las renderiza con estos huecos.
    blanks: tuple[BlankRendicion, ...] = ()


# Tipos de blank donde el alumno ELIGE de una lista. En el resto (shortanswer,
# numerical) escribe libremente y las opciones son las respuestas aceptadas: D3
# prohíbe mandarlas. "matching" (C-78, emparejamiento) TAMBIÉN elige de una
# lista (el pool de respuestas de la pregunta) — sin esto, el <select> del
# alumno llegaría vacío y la pregunta sería imposible de responder.
_BLANK_CON_OPCIONES = ("multichoice", "multichoice_nocase", "multiresponse", "matching")


def _proyectar_blank(blank) -> BlankRendicion:
    expone_opciones = blank.tipo.lower() in _BLANK_CON_OPCIONES
    return BlankRendicion(
        id=blank.id or "",
        orden=blank.orden,
        tipo=blank.tipo,
        texto_antes=blank.texto_antes,
        texto_despues=blank.texto_despues,
        opciones=tuple(
            OpcionRendicion(id=o.id or "", texto=o.texto, orden=o.orden)
            for o in sorted(blank.opciones, key=lambda x: x.orden)
        )
        if expone_opciones
        else (),
    )


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


def proyectar_examen(
    examen: ExamenContenido, *, ya_filtrado: bool = False
) -> ExamenRendicion:
    """Proyecta un ExamenContenido a ExamenRendicion, excluyendo es_correcta (D3).

    El orden de preguntas y opciones es estable (por ``orden`` ascendente).

    Opción B (pool de preguntas): solo se proyectan las preguntas seleccionadas
    por el docente (``seleccionada=True``). Las del pool no seleccionadas NO viajan
    a la rendición del alumno.

    ``ya_filtrado`` (c-78 E-07): con sorteo por intento el recorte ya lo hizo el
    repositorio contra el set del intento, y el pool entero está con
    `seleccionada=False` — volver a filtrar acá dejaría al alumno sin preguntas.
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
            blanks=tuple(
                _proyectar_blank(b) for b in sorted(p.blanks, key=lambda x: x.orden)
            ),
        )
        for p in sorted(examen.preguntas, key=lambda x: x.orden)
        if ya_filtrado or p.seleccionada
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

    async def obtener_para_rendir(
        self, examen_id: str, pregunta_ids: list[str] | None = None
    ) -> ExamenRendicion | None:
        """Devuelve la proyección sin es_correcta, o None si el examen no existe.

        Freeze (C-72 §17): si el examen pertenece a una COMISIÓN desactivada eleva
        ``ComisionInactivaError``; si su MATERIA está desactivada eleva
        ``MateriaInactivaError``. En ambos casos no se puede iniciar la rendición.

        ``pregunta_ids`` (c-78 E-07): el set sorteado para ESTE intento. None =
        modo 'fijo', se resuelve por `seleccionada` como siempre.
        """
        # Lectura acotada: filtra las preguntas en SQL y trae los blanks cloze.
        # Fallback a obtener() para dobles de test que solo implementan el mínimo.
        leer = getattr(self._repo, "obtener_para_rendir", None)
        if leer is None:
            examen = await self._repo.obtener(examen_id)
        elif pregunta_ids is not None:
            examen = await leer(examen_id, pregunta_ids)
        else:
            examen = await leer(examen_id)
        if examen is None:
            return None
        await self._verificar_materia_activa(examen)
        return proyectar_examen(examen, ya_filtrado=pregunta_ids is not None)

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
        # Freeze a nivel comisión (baja lógica): congela SOLO sus exámenes.
        if not comision.activa:
            raise ComisionInactivaError(
                f"La comisión {comision.nombre!r} está desactivada: no se puede "
                "iniciar la rendición de sus exámenes."
            )
        materia = await self._materia_repo.obtener(comision.materia_id)
        if materia is not None and not materia.activa:
            raise MateriaInactivaError(
                f"La materia {materia.nombre!r} está desactivada: no se puede "
                "iniciar la rendición de sus exámenes."
            )
