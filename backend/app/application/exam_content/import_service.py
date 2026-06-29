"""Servicio de importación de Moodle XML → ExamenContenido (C-69).

Orquesta: parse XML → validar preguntas → persistir → reporte.
Preguntas que no superan la validación de dominio se reportan como omitidas
sin abortar la importación.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.exam_content.moodle_parser import PreguntaData, PreguntaOmitida, parse_moodle_xml
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.domain.exam_content.errors import PreguntaInvalidaError
from app.domain.exam_content.ports import AbstractExamenContenidoRepository


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
    ) -> ImportReport:
        """Parsea XML, valida preguntas y persiste el examen.

        D12 (parte B): moodle_courseid/moodle_cmid fijan el destino del write-back
        de nota POR EXAMEN. Si quedan en None, el write-back cae al global (compat).

        Raises:
            MoodleXmlInvalidoError: si el XML es malformado.
            MoodleXmlVacioError: si no hay preguntas soportadas.
        """
        parse_result = parse_moodle_xml(xml_bytes)

        omitidas: list[OmitidaItem] = [
            OmitidaItem(tipo=o.tipo, nombre=o.nombre, motivo="tipo no soportado")
            for o in parse_result.omitidas
        ]

        preguntas_validas: list[Pregunta] = []
        for p_data in parse_result.preguntas:
            try:
                pregunta = _pregunta_data_to_entity(p_data)
                preguntas_validas.append(pregunta)
            except PreguntaInvalidaError as exc:
                omitidas.append(
                    OmitidaItem(
                        tipo=p_data.tipo,
                        nombre=p_data.enunciado[:60],
                        motivo=str(exc),
                    )
                )

        examen = ExamenContenido(
            titulo=titulo or "Examen importado",
            preguntas=tuple(preguntas_validas),
            comision_id=None,  # D11: se asocia en sección 6
            moodle_courseid=moodle_courseid,  # D12: destino por examen (None = global)
            moodle_cmid=moodle_cmid,
        )
        guardado = await self._repo.guardar(examen)

        return ImportReport(
            examen_id=guardado.id,
            importadas=len(preguntas_validas),
            omitidas=omitidas,
        )


def _pregunta_data_to_entity(p: PreguntaData) -> Pregunta:
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
    )
