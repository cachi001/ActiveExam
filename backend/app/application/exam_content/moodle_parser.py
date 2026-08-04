"""Parser de Moodle XML → estructuras de dominio de exam_content (C-69, C-74).

Soporta: multichoice, truefalse, cloze/multianswer.
Omite: essay y cualquier tipo desconocido.
Trackea: category → categoria_ruta por pregunta (C-74 §2.2).

Cloze (C-74 §5):
  Sintaxis de blank: {N:TIPO:OPC1~OPC2~...}
  Tipos soportados: MULTICHOICE, MULTICHOICE_S, SHORTANSWER.
  Cada opcion puede tener prefijo de correccion:
    =texto     → 100% correcto
    %N%texto   → N% de peso (N=100 → correcto)
    texto      → 0% (incorrecto, sin prefijo)
  Variantes NO soportadas en esta primera vuelta: NUMERICAL, ESSAY.

_strip_html elimina <tags> pero NO toca {N:TYPE:...} (usan {}, no <>) —
los placeholders cloze sobreviven intactos al strip.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.application.exam_content.errors import MoodleXmlInvalidoError, MoodleXmlVacioError

_TIPOS_SOPORTADOS = frozenset({"multichoice", "truefalse", "cloze", "multianswer"})

_RE_BLANK = re.compile(r"\{(\d+):(MULTICHOICE_S|MULTICHOICE|SHORTANSWER):([^}]*)\}", re.IGNORECASE)
_RE_OPT_PESO = re.compile(r"^%(\d+)%(.*)$", re.DOTALL)


@dataclass
class OpcionClozeDato:
    """Opcion de un blank dentro de una pregunta cloze."""
    texto: str
    es_correcta: bool
    peso: int
    orden: int


@dataclass
class BlankData:
    """Hueco (blank) dentro de un texto cloze."""
    orden: int
    tipo: str
    texto_antes: str
    texto_despues: str
    opciones: list[OpcionClozeDato] = field(default_factory=list)


def _parse_opcion_cloze(raw: str) -> tuple[str, int]:
    texto = raw.strip()
    if texto.startswith("="):
        return html.unescape(texto[1:].strip()), 100
    m = _RE_OPT_PESO.match(texto)
    if m:
        return html.unescape(m.group(2).strip()), int(m.group(1))
    return html.unescape(texto), 0


def parse_cloze_blanks(texto_cloze: str) -> list[BlankData]:
    """Extrae los blanks de un texto cloze.

    Materializa los matches primero para poder acceder al anterior/siguiente
    sin re-ejecutar finditer (iterador de un solo uso).
    """
    blanks: list[BlankData] = []
    matches = list(_RE_BLANK.finditer(texto_cloze))

    for i, m in enumerate(matches):
        tipo_raw = m.group(2).upper()
        tipo = "shortanswer" if "SHORT" in tipo_raw else "multichoice"

        opciones: list[OpcionClozeDato] = []
        for j, opt_raw in enumerate(m.group(3).split("~")):
            texto_opt, peso = _parse_opcion_cloze(opt_raw)
            if texto_opt:
                opciones.append(OpcionClozeDato(
                    texto=texto_opt,
                    es_correcta=peso >= 100,
                    peso=peso,
                    orden=j,
                ))

        inicio_anterior = matches[i - 1].end() if i > 0 else 0
        fin_siguiente = matches[i + 1].start() if i + 1 < len(matches) else len(texto_cloze)

        blanks.append(BlankData(
            orden=i,
            tipo=tipo,
            texto_antes=texto_cloze[inicio_anterior:m.start()],
            texto_despues=texto_cloze[m.end():fin_siguiente],
            opciones=opciones,
        ))

    return blanks


_TRUE_FALSE_MAP = {"true": "Verdadero", "false": "Falso"}


def _strip_html(text: str) -> str:
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
    categoria_ruta: list[str] | None = None
    blanks: list[BlankData] = field(default_factory=list)


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
    categoria_activa: list[str] | None = None

    for i, question in enumerate(root.findall("question")):
        tipo = question.get("type", "")

        if tipo == "category":
            cat_el = question.find("category/text")
            if cat_el is not None and cat_el.text:
                ruta = cat_el.text.strip()
                for prefix in ("$course$/top/", "$course$/"):
                    if ruta.startswith(prefix):
                        ruta = ruta[len(prefix):]
                        break
                segmentos = [s.strip() for s in ruta.split("/") if s.strip()]
                categoria_activa = segmentos if segmentos else None
            continue

        nombre_el = question.find("name/text")
        nombre = nombre_el.text if nombre_el is not None and nombre_el.text else f"pregunta_{i}"

        if tipo not in _TIPOS_SOPORTADOS:
            omitidas.append(PreguntaOmitida(tipo=tipo, nombre=nombre))
            continue

        if tipo in ("cloze", "multianswer"):
            preguntas.append(_parse_cloze(question, categoria_activa, len(preguntas)))
        else:
            enunciado = _parse_enunciado(question)
            opciones = _parse_opciones(question, tipo)
            preguntas.append(
                PreguntaData(
                    enunciado=enunciado,
                    tipo=tipo,
                    opciones=opciones,
                    orden=len(preguntas),
                    categoria_ruta=list(categoria_activa) if categoria_activa else None,
                )
            )

    if not preguntas:
        raise MoodleXmlVacioError("El XML no contiene preguntas de tipo soportado.")

    return ParseResult(preguntas=preguntas, omitidas=omitidas)


def _parse_cloze(
    question: ET.Element,
    categoria_activa: list[str] | None,
    orden: int,
) -> PreguntaData:
    text_el = question.find("questiontext/text")
    raw_text = text_el.text if text_el is not None and text_el.text else ""
    enunciado = _strip_html(raw_text)
    blanks = parse_cloze_blanks(enunciado)
    return PreguntaData(
        enunciado=enunciado,
        tipo="cloze",
        opciones=[],
        orden=orden,
        categoria_ruta=list(categoria_activa) if categoria_activa else None,
        blanks=blanks,
    )


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
