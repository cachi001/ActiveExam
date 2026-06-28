"""Parser de Moodle XML → estructuras de dominio de exam_content (C-69).

Soporta: multichoice, truefalse.
Omite: category (silenciosamente), cloze, essay y cualquier tipo desconocido.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.application.exam_content.errors import MoodleXmlInvalidoError, MoodleXmlVacioError

_TIPOS_SOPORTADOS = frozenset({"multichoice", "truefalse"})
_TRUE_FALSE_MAP = {"true": "Verdadero", "false": "Falso"}


def _strip_html(text: str) -> str:
    """Elimina tags HTML y retorna texto limpio."""
    return re.sub(r"<[^>]+>", "", text).strip()


@dataclass
class OpcionData:
    texto: str
    es_correcta: bool
    orden: int = 0


@dataclass
class PreguntaData:
    enunciado: str
    tipo: str
    opciones: list[OpcionData] = field(default_factory=list)
    orden: int = 0


@dataclass
class PreguntaOmitida:
    tipo: str
    nombre: str


@dataclass
class ParseResult:
    preguntas: list[PreguntaData]
    omitidas: list[PreguntaOmitida]


def parse_moodle_xml(xml_bytes: bytes) -> ParseResult:
    """Parsea un export Moodle XML y devuelve preguntas + omitidas.

    Raises:
        MoodleXmlInvalidoError: si el XML es malformado.
        MoodleXmlVacioError: si no hay preguntas de tipo soportado.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise MoodleXmlInvalidoError(f"XML malformado: {exc}") from exc

    preguntas: list[PreguntaData] = []
    omitidas: list[PreguntaOmitida] = []

    for i, question in enumerate(root.findall("question")):
        tipo = question.get("type", "")

        if tipo == "category":
            continue

        nombre_el = question.find("name/text")
        nombre = nombre_el.text if nombre_el is not None and nombre_el.text else f"pregunta_{i}"

        if tipo not in _TIPOS_SOPORTADOS:
            omitidas.append(PreguntaOmitida(tipo=tipo, nombre=nombre))
            continue

        enunciado = _parse_enunciado(question)
        opciones = _parse_opciones(question, tipo)

        preguntas.append(
            PreguntaData(
                enunciado=enunciado,
                tipo=tipo,
                opciones=opciones,
                orden=len(preguntas),
            )
        )

    if not preguntas:
        raise MoodleXmlVacioError("El XML no contiene preguntas de tipo soportado.")

    return ParseResult(preguntas=preguntas, omitidas=omitidas)


def _parse_enunciado(question: ET.Element) -> str:
    text_el = question.find("questiontext/text")
    if text_el is None or not text_el.text:
        return ""
    return _strip_html(text_el.text)


def _parse_opciones(question: ET.Element, tipo: str) -> list[OpcionData]:
    opciones: list[OpcionData] = []
    for j, answer in enumerate(question.findall("answer")):
        fraction_str = answer.get("fraction", "0")
        try:
            fraction = float(fraction_str)
        except ValueError:
            fraction = 0.0

        text_el = answer.find("text")
        raw_text = text_el.text if text_el is not None and text_el.text else ""
        texto = _strip_html(raw_text)

        if tipo == "truefalse":
            texto = _TRUE_FALSE_MAP.get(texto.lower(), texto)

        opciones.append(
            OpcionData(
                texto=texto,
                es_correcta=fraction > 0,
                orden=j,
            )
        )
    return opciones
