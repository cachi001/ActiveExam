"""2.1 RED → 2.2 GREEN → 2.8 TRIANGULATE: tests del parser Moodle XML.

No necesitan DB. Usan fixtures en tests/fixtures/moodle/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.exam_content.errors import MoodleXmlInvalidoError, MoodleXmlVacioError
from app.application.exam_content.moodle_parser import parse_moodle_xml

FIXTURES = Path(__file__).parent / "fixtures" / "moodle"


# ---------------------------------------------------------------------------
# 2.1 RED — fixture real con multichoice + truefalse + category
# ---------------------------------------------------------------------------


def test_parse_multichoice_y_truefalse():
    """El XML de muestra tiene: category (skip), multichoice, truefalse."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    result = parse_moodle_xml(xml)

    assert len(result.preguntas) == 2

    mc = next(p for p in result.preguntas if p.tipo == "multichoice")
    assert "Francia" in mc.enunciado or "capital" in mc.enunciado.lower()
    assert sum(1 for o in mc.opciones if o.es_correcta) == 1
    correcta = next(o for o in mc.opciones if o.es_correcta)
    assert "Par" in correcta.texto  # "París"

    tf = next(p for p in result.preguntas if p.tipo == "truefalse")
    assert len(tf.opciones) == 2
    assert sum(1 for o in tf.opciones if o.es_correcta) == 1


def test_category_se_omite_silenciosamente():
    """Las preguntas type='category' se descartan sin llegar a omitidas."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    result = parse_moodle_xml(xml)
    tipos_omitidos = [o.tipo for o in result.omitidas]
    assert "category" not in tipos_omitidos


def test_xml_invalido_lanza_error():
    with pytest.raises(MoodleXmlInvalidoError):
        parse_moodle_xml(b"not xml at all <<<<")


def test_xml_vacio_lanza_error():
    """XML bien formado pero sin preguntas soportadas → MoodleXmlVacioError."""
    xml = (FIXTURES / "invalid_empty.xml").read_bytes()
    with pytest.raises(MoodleXmlVacioError):
        parse_moodle_xml(xml)


# ---------------------------------------------------------------------------
# 2.8 TRIANGULATE — XML mixto: soportados + no soportados
# ---------------------------------------------------------------------------


def test_parse_unsupported_omitted():
    """XML mixto: multichoice OK + cloze + essay → cloze/essay van a omitidas."""
    xml = (FIXTURES / "mixed_unsupported.xml").read_bytes()
    result = parse_moodle_xml(xml)

    assert len(result.preguntas) >= 1
    assert any(o.tipo in ("cloze", "essay") for o in result.omitidas)


def test_parse_mixed_importadas_y_omitidas():
    """Verifica recuento exacto de importadas vs omitidas en XML mixto."""
    xml = (FIXTURES / "mixed_unsupported.xml").read_bytes()
    result = parse_moodle_xml(xml)

    assert len(result.preguntas) == 1  # solo el multichoice
    assert len(result.omitidas) == 2   # cloze + essay


def test_truefalse_texto_mapeado():
    """truefalse: 'true' se mapea a 'Verdadero', 'false' a 'Falso'."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    result = parse_moodle_xml(xml)

    tf = next(p for p in result.preguntas if p.tipo == "truefalse")
    textos = {o.texto for o in tf.opciones}
    assert textos == {"Verdadero", "Falso"}


def test_html_stripped_from_enunciado():
    """El HTML en questiontext se limpia y el enunciado no tiene tags."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    result = parse_moodle_xml(xml)

    mc = next(p for p in result.preguntas if p.tipo == "multichoice")
    assert "<" not in mc.enunciado
    assert ">" not in mc.enunciado
