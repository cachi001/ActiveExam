"""C-78: soporte de preguntas matching (emparejamiento) y shortanswer (respuesta
corta) en el import XML.

Pentest/pedido real (2026-08-21, campus FRM): con el export real de "Programación
3-2026 Agosto" 24/175 preguntas se perdían por tipos no soportados (15 matching,
9 shortanswer). Ambos se normalizan a tipo="cloze" — mismo modelo de blanks,
misma UI de rendición (PreguntaCloze.tsx), misma corrección server-side
(grade_calculator._blank_acertado) y misma revisión (revision_query.py) que ya
existen para cloze real y ddwtos — sin tabla ni tipo nuevo.

matching: cada <subquestion> (estímulo + respuesta) se normaliza a un blank
tipo="matching" cuyas opciones son el POOL de todas las respuestas de la
pregunta (igual que Moodle, que baraja las respuestas entre pares) — se
resuelve por id, igual que un blank multichoice (grade_calculator agrega
"matching" a _BLANK_ELIGE_OPCION).

shortanswer: se normaliza a un cloze de UN blank tipo="shortanswer" — reusa
directo la rama de blank de texto libre (_blank_acertado ya compara
case-insensitive contra las opciones marcadas es_correcta, sin cambios).
"""

from __future__ import annotations

from app.application.exam_content.moodle_parser import parse_moodle_xml

XML_MATCHING_BASICO = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="matching">
    <name><text>lenguajes_paradigma</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>Une cada lenguaje con su paradigma principal.</p>]]></text>
    </questiontext>
    <subquestion format="html">
      <text><![CDATA[<p>Python</p>]]></text>
      <answer><text>Multiparadigma</text></answer>
    </subquestion>
    <subquestion format="html">
      <text><![CDATA[<p>Haskell</p>]]></text>
      <answer><text>Funcional</text></answer>
    </subquestion>
    <subquestion format="html">
      <text><![CDATA[<p>Prolog</p>]]></text>
      <answer><text>Logico</text></answer>
    </subquestion>
  </question>
</quiz>
"""

XML_MATCHING_UN_SOLO_PAR = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="matching">
    <name><text>rota</text></name>
    <questiontext format="html"><text><![CDATA[<p>Solo un par.</p>]]></text></questiontext>
    <subquestion format="html">
      <text><![CDATA[<p>Python</p>]]></text>
      <answer><text>Multiparadigma</text></answer>
    </subquestion>
  </question>
  <question type="multichoice">
    <name><text>Buena</text></name>
    <questiontext format="html"><text>Enunciado valido</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

XML_SHORTANSWER_BASICO = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="shortanswer">
    <name><text>funcion_len</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>&iquest;Como se llama la funcion para obtener la longitud de una lista?</p>]]></text>
    </questiontext>
    <usecase>0</usecase>
    <answer fraction="100" format="moodle_auto_format"><text>len</text></answer>
    <answer fraction="50" format="moodle_auto_format"><text>length</text></answer>
  </question>
</quiz>
"""

XML_SHORTANSWER_SIN_CORRECTA = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="shortanswer">
    <name><text>rota</text></name>
    <questiontext format="html"><text><![CDATA[<p>Sin respuesta correcta.</p>]]></text></questiontext>
    <answer fraction="0"><text>cualquiera</text></answer>
  </question>
  <question type="multichoice">
    <name><text>Buena</text></name>
    <questiontext format="html"><text>Enunciado valido</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""


def test_matching_se_normaliza_a_cloze_con_un_blank_por_par():
    """RED→GREEN: 3 subquestions → 3 blanks tipo='matching', 1 respuesta correcta cada uno."""
    result = parse_moodle_xml(XML_MATCHING_BASICO)

    assert result.omitidas == []
    assert len(result.preguntas) == 1
    p = result.preguntas[0]
    assert p.tipo == "cloze"
    assert len(p.blanks) == 3
    for blank in p.blanks:
        assert blank.tipo == "matching"


def test_matching_el_pool_de_respuestas_incluye_las_de_los_otros_pares():
    """TRIANGULATE: cada blank ofrece el pool COMPLETO de respuestas (como Moodle
    baraja entre pares) pero con exactamente 1 marcada correcta — LA SUYA."""
    result = parse_moodle_xml(XML_MATCHING_BASICO)
    p = result.preguntas[0]

    for blank, esperada in zip(p.blanks, ["Multiparadigma", "Funcional", "Logico"]):
        textos = {o.texto for o in blank.opciones}
        assert textos == {"Multiparadigma", "Funcional", "Logico"}
        correctas = [o.texto for o in blank.opciones if o.es_correcta]
        assert correctas == [esperada]


def test_matching_el_estimulo_queda_en_texto_antes_del_blank():
    """El texto antes de cada blank es el estimulo (columna izquierda) del par."""
    result = parse_moodle_xml(XML_MATCHING_BASICO)
    p = result.preguntas[0]

    assert "Python" in p.blanks[0].texto_antes
    assert "Haskell" in p.blanks[1].texto_antes
    assert "Prolog" in p.blanks[2].texto_antes


def test_matching_con_menos_de_2_pares_se_omite():
    """TRIANGULATE: un solo par no es un emparejamiento real → se omite."""
    result = parse_moodle_xml(XML_MATCHING_UN_SOLO_PAR)

    assert len(result.preguntas) == 1  # solo la multichoice válida
    assert result.preguntas[0].enunciado == "Enunciado valido"
    assert len(result.omitidas) == 1
    assert result.omitidas[0].tipo == "matching"


def test_shortanswer_se_normaliza_a_cloze_de_un_blank():
    """RED→GREEN: shortanswer → cloze de 1 blank tipo='shortanswer'."""
    result = parse_moodle_xml(XML_SHORTANSWER_BASICO)

    assert result.omitidas == []
    assert len(result.preguntas) == 1
    p = result.preguntas[0]
    assert p.tipo == "cloze"
    assert len(p.blanks) == 1
    blank = p.blanks[0]
    assert blank.tipo == "shortanswer"


def test_shortanswer_todas_las_respuestas_aceptadas_quedan_como_opciones():
    """TRIANGULATE: 'len' (100%) y 'length' (50%) son ambas respuestas
    aceptadas — ambas correctas, sin distinción de peso en la aceptación."""
    result = parse_moodle_xml(XML_SHORTANSWER_BASICO)
    blank = result.preguntas[0].blanks[0]

    correctas = {o.texto for o in blank.opciones if o.es_correcta}
    assert correctas == {"len", "length"}


def test_shortanswer_sin_respuesta_correcta_se_omite():
    """TRIANGULATE: ninguna respuesta con fraction>0 → no hay nada aceptable, se omite."""
    result = parse_moodle_xml(XML_SHORTANSWER_SIN_CORRECTA)

    assert len(result.preguntas) == 1  # solo la multichoice válida
    assert result.preguntas[0].enunciado == "Enunciado valido"
    assert len(result.omitidas) == 1
    assert result.omitidas[0].tipo == "shortanswer"
