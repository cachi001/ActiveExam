"""Servicio de importación de Moodle XML → ExamenContenido (C-69, C-74).

Orquesta: parse XML → validar preguntas → resolver categorías → persistir → reporte.
Preguntas que no superan la validación de dominio se reportan como omitidas
sin abortar la importación.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import uuid

import sqlalchemy as sa

from app.application.exam_content.errors import LimitePreguntasExcedidoError
from app.application.exam_content.moodle_parser import BlankData, PreguntaData, PreguntaOmitida, parse_moodle_xml
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.domain.exam_content.errors import PreguntaInvalidaError
from app.domain.exam_content.ports import AbstractExamenContenidoRepository
from app.infrastructure.persistence.repositories.categoria_pregunta import (
    CategoriaPreguntaSqlRepository,
)

# Tope duro del sistema: ningún examen puede importar más preguntas que esto, se
# pida el tope que se pida. Protege de un XML enorme (accidental o no) que haría
# impracticable la pantalla de selección y la rendición.
LIMITE_PREGUNTAS_SISTEMA = 500


@dataclass
class OmitidaItem:
    tipo: str
    nombre: str
    motivo: str = ""


@dataclass
class ImportReport:
    examen_id: str
    importadas: int
    omitidas: list[OmitidaItem] = field(default_factory=list)


class ImportacionMoodleService:
    """Caso de uso: importar examen desde Moodle XML."""

    def __init__(self, repo: AbstractExamenContenidoRepository) -> None:
        self._repo = repo

    async def importar(
        self,
        xml_bytes: bytes,
        titulo: str | None = None,
        *,
        moodle_courseid: int | None = None,
        moodle_cmid: int | None = None,
        moodle_component: str | None = None,
        limite_preguntas: int | None = None,
        materia_id: str | None = None,
    ) -> ImportReport:
        """Parsea XML, valida preguntas y persiste el examen.

        D12 (parte B): moodle_courseid/moodle_cmid fijan el destino del write-back
        de nota POR EXAMEN. Si quedan en None, el write-back cae al global (compat).

        ``limite_preguntas``: tope de preguntas del examen. None = solo aplica el
        tope duro del sistema. Si el XML trae más preguntas válidas que el tope, la
        importación se RECHAZA entera (no se truncan: ver LimitePreguntasExcedidoError).

        ``materia_id``: si se provee, resuelve/crea la jerarquía de categorías
        (C-74) y asigna `categoria_id` a cada pregunta según su `categoria_ruta`.

        Raises:
            MoodleXmlInvalidoError: si el XML es malformado.
            MoodleXmlVacioError: si no hay preguntas soportadas.
            LimitePreguntasExcedidoError: si las preguntas válidas superan el tope.
        """
        parse_result = parse_moodle_xml(xml_bytes)

        omitidas: list[OmitidaItem] = [
            OmitidaItem(tipo=o.tipo, nombre=o.nombre, motivo="tipo no soportado")
            for o in parse_result.omitidas
        ]

        # C-74 §2.3: resolver jerarquía de categorías si se provee materia_id.
        # Memo: ruta_tuple → categoria_id para evitar round-trips repetidos.
        cat_repo: CategoriaPreguntaSqlRepository | None = None
        ruta_memo: dict[tuple[str, ...], str] = {}
        if materia_id:
            session = getattr(self._repo, "_db", None)
            if session is not None:
                cat_repo = CategoriaPreguntaSqlRepository(session)

        preguntas_validas: list[Pregunta] = []
        blanks_por_pregunta: list[list[BlankData]] = []
        for p_data in parse_result.preguntas:
            try:
                categoria_id: str | None = None
                if cat_repo and materia_id and p_data.categoria_ruta:
                    categoria_id = await _resolver_ruta(
                        cat_repo, materia_id, p_data.categoria_ruta, ruta_memo
                    )
                pregunta = _pregunta_data_to_entity(p_data, categoria_id=categoria_id)
                preguntas_validas.append(pregunta)
                blanks_por_pregunta.append(p_data.blanks)
            except PreguntaInvalidaError as exc:
                omitidas.append(
                    OmitidaItem(
                        tipo=p_data.tipo,
                        nombre=p_data.enunciado[:60],
                        motivo=str(exc),
                    )
                )

        # Tope efectivo: el que pidió el docente, acotado por el tope del sistema.
        # Se evalúa sobre las preguntas VÁLIDAS (las omitidas no forman el examen).
        tope = min(limite_preguntas or LIMITE_PREGUNTAS_SISTEMA, LIMITE_PREGUNTAS_SISTEMA)
        if len(preguntas_validas) > tope:
            raise LimitePreguntasExcedidoError(len(preguntas_validas), tope)

        examen = ExamenContenido(
            titulo=titulo or "Examen importado",
            preguntas=tuple(preguntas_validas),
            limite_preguntas=limite_preguntas,
            comision_id=None,  # D11: se asocia en sección 6
            moodle_courseid=moodle_courseid,  # D12: destino por examen (None = global)
            moodle_cmid=moodle_cmid,
            moodle_component=moodle_component,  # C-73: mod_assign|mod_quiz (None = global)
        )
        guardado = await self._repo.guardar(examen)

        session = getattr(self._repo, "_db", None)
        if session is not None:
            for pregunta, blanks in zip(guardado.preguntas, blanks_por_pregunta):
                if blanks:
                    await _persistir_blanks_cloze(session, pregunta.id, blanks)

        return ImportReport(
            examen_id=guardado.id,
            importadas=len(preguntas_validas),
            omitidas=omitidas,
        )


async def _resolver_ruta(
    cat_repo: CategoriaPreguntaSqlRepository,
    materia_id: str,
    ruta: list[str],
    memo: dict[tuple[str, ...], str],
) -> str:
    """Resuelve (o crea) la jerarquía de categorías para una ruta dada.

    Recorre los segmentos de la ruta de izquierda a derecha, creando cada nivel
    si no existe. El memo evita consultas repetidas para la misma sub-ruta.
    Devuelve el id de la categoría hoja.
    """
    padre_id: str | None = None
    for i, segmento in enumerate(ruta):
        parcial = tuple(ruta[: i + 1])
        if parcial in memo:
            padre_id = memo[parcial]
        else:
            cat = await cat_repo.resolver_o_crear(materia_id, segmento, padre_id)
            memo[parcial] = cat.id
            padre_id = cat.id
    return padre_id  # type: ignore[return-value]  # ruta no vacía garantizada por el caller


def _pregunta_data_to_entity(p: PreguntaData, *, categoria_id: str | None = None) -> Pregunta:
    opciones = tuple(
        OpcionRespuesta(
            texto=o.texto,
            es_correcta=o.es_correcta,
            orden=o.orden,
        )
        for o in p.opciones
    )
    return Pregunta(
        enunciado=p.enunciado,
        tipo=p.tipo,
        opciones=opciones,
        orden=p.orden,
        categoria_id=categoria_id,
    )


async def _persistir_blanks_cloze(session, pregunta_id: str, blanks: list) -> None:
    """Inserta los blanks cloze (y sus opciones) para una pregunta ya guardada."""
    for blank in blanks:
        blank_id = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo, texto_antes, texto_despues) "
                "VALUES (:id, :pregunta_id, :orden, :tipo, :texto_antes, :texto_despues)"
            ),
            {
                "id": blank_id,
                "pregunta_id": pregunta_id,
                "orden": blank.orden,
                "tipo": blank.tipo,
                "texto_antes": blank.texto_antes or None,
                "texto_despues": blank.texto_despues or None,
            },
        )
        for opcion in blank.opciones:
            await session.execute(
                sa.text(
                    "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso) "
                    "VALUES (:id, :blank_id, :texto, :es_correcta, :peso)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "blank_id": blank_id,
                    "texto": opcion.texto,
                    "es_correcta": opcion.es_correcta,
                    "peso": opcion.peso,
                },
            )
