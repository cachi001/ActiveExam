"""C-74: soporte de preguntas ddwtos (drag and drop into text) en el import XML.

ddwtos no tiene un tag explícito de mapeo dragbox→blank en el export de Moodle;
se parsea al mismo modelo de blanks MULTICHOICE que cloze, asumiendo que los
primeros N dragboxes (orden de documento) son la respuesta correcta de
[[1]]..[[N]] en ese orden (ver docstring de moodle_parser.py para el porqué).
Se normaliza a tipo="cloze" — misma UI de rendición, misma corrección
server-side.
"""

from __future__ import annotations

from app.application.exam_content.moodle_parser import parse_moodle_xml

XML_DDWTOS_SIN_DISTRACTORES = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="ddwtos">
    <name><text>orden_sentencias</text></name>
    <questiontext format="html">
      <text><![CDATA[<ol><li>[[1]]</li><li>[[2]]</li><li>[[3]]</li></ol>]]></text>
    </questiontext>
    <dragbox><text>B = 5</text><group>1</group></dragbox>
    <dragbox><text>C = B + 3</text><group>1</group></dragbox>
    <dragbox><text>A = B * C</text><group>1</group></dragbox>
  </question>
</quiz>
"""

XML_DDWTOS_CON_DISTRACTORES = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="ddwtos">
    <name><text>operadores</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>and: [[1]]</p><p>or: [[2]]</p>]]></text>
    </questiontext>
    <dragbox><text>and</text><group>1</group></dragbox>
    <dragbox><text>or</text><group>1</group></dragbox>
    <dragbox><text>not</text><group>1</group></dragbox>
    <dragbox><text>==</text><group>1</group></dragbox>
  </question>
</quiz>
"""

XML_DDWTOS_SIN_SUFICIENTES_DRAGBOX = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="ddwtos">
    <name><text>rota</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>[[1]] y [[2]] y [[3]]</p>]]></text>
    </questiontext>
    <dragbox><text>uno</text><group>1</group></dragbox>
  </question>
  <question type="multichoice">
    <name><text>Buena</text></name>
    <questiontext format="html"><text>Enunciado valido</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

XML_DDWTOS_SIN_PLACEHOLDERS = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="ddwtos">
    <name><text>sin_huecos</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>Sin ningun placeholder aca.</p>]]></text>
    </questiontext>
    <dragbox><text>x</text><group>1</group></dragbox>
  </question>
  <question type="multichoice">
    <name><text>Buena</text></name>
    <questiontext format="html"><text>Enunciado valido</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""


def test_ddwtos_sin_distractores_mapea_en_orden():
    """RED→GREEN: N placeholders + N dragboxes → cada blank toma el dragbox de su posición."""
    result = parse_moodle_xml(XML_DDWTOS_SIN_DISTRACTORES)

    assert result.omitidas == []
    assert len(result.preguntas) == 1
    p = result.preguntas[0]
    assert p.tipo == "cloze"
    assert len(p.blanks) == 3

    for blank, esperado in zip(p.blanks, ["B = 5", "C = B + 3", "A = B * C"]):
        assert blank.tipo == "multichoice"
        correctas = [o.texto for o in blank.opciones if o.es_correcta]
        assert correctas == [esperado]


def test_ddwtos_con_distractores_quedan_en_todos_los_blanks():
    """TRIANGULATE: dragboxes de más (distractores) aparecen como opción incorrecta en TODOS los blanks."""
    result = parse_moodle_xml(XML_DDWTOS_CON_DISTRACTORES)

    assert len(result.preguntas) == 1
    p = result.preguntas[0]
    assert len(p.blanks) == 2

    blank1, blank2 = p.blanks
    assert {o.texto for o in blank1.opciones} == {"and", "or", "not", "=="}
    assert [o.texto for o in blank1.opciones if o.es_correcta] == ["and"]
    assert {o.texto for o in blank2.opciones} == {"and", "or", "not", "=="}
    assert [o.texto for o in blank2.opciones if o.es_correcta] == ["or"]


def test_ddwtos_sin_suficientes_dragbox_se_omite():
    """TRIANGULATE: menos dragboxes que placeholders → se omite (no se arriesga una clave incorrecta)."""
    result = parse_moodle_xml(XML_DDWTOS_SIN_SUFICIENTES_DRAGBOX)

    assert len(result.preguntas) == 1  # solo la multichoice válida
    assert result.preguntas[0].enunciado == "Enunciado valido"
    assert len(result.omitidas) == 1
    assert result.omitidas[0].tipo == "ddwtos"


def test_ddwtos_sin_placeholders_se_omite():
    """TRIANGULATE: ddwtos sin [[N]] en el texto no tiene nada que mapear → se omite."""
    result = parse_moodle_xml(XML_DDWTOS_SIN_PLACEHOLDERS)

    assert len(result.preguntas) == 1
    assert len(result.omitidas) == 1
    assert result.omitidas[0].tipo == "ddwtos"
