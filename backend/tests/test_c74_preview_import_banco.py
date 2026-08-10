"""C-74: preview de un XML antes de importarlo al banco — sin tocar la DB.

`preview_import_banco` es pura: parsea y agrupa por categoría/tipo, pero no
abre sesión ni persiste nada. Se usa para mostrarle al docente qué va a entrar
al banco (árbol de categorías + conteo por tipo) ANTES de confirmar el import.
"""

from __future__ import annotations

from app.application.exam_content.import_service import preview_import_banco

XML_MIXTO = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>P1</text></name>
    <questiontext format="html"><text>Enunciado 1</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="truefalse">
    <name><text>P2</text></name>
    <questiontext format="html"><text>Enunciado 2</text></questiontext>
    <answer fraction="100"><text>Verdadero</text></answer>
    <answer fraction="0"><text>Falso</text></answer>
  </question>
  <question type="category">
    <category><text>$course$/top/Unidad 2/Tema 2.1</text></category>
  </question>
  <question type="multichoice">
    <name><text>P3</text></name>
    <questiontext format="html"><text>Enunciado 3</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

XML_SIN_CATEGORIA = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Suelta</text></name>
    <questiontext format="html"><text>Sin categoria</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

XML_CON_INVALIDA = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Rota</text></name>
    <questiontext format="html"><text>Sin respuesta correcta</text></questiontext>
    <answer fraction="0"><text>A</text></answer>
    <answer fraction="0"><text>B</text></answer>
  </question>
</quiz>
"""


def test_preview_agrupa_por_ruta_y_tipo():
    """RED→GREEN: el preview arma el árbol con conteo por tipo, sin tocar DB."""
    report = preview_import_banco(XML_MIXTO)

    assert report.total_preguntas == 3
    assert len(report.categorias) == 2

    por_ruta = {tuple(c.ruta): c.preguntas_por_tipo for c in report.categorias}
    assert por_ruta[("Unidad 1",)] == {"multichoice": 1, "truefalse": 1}
    assert por_ruta[("Unidad 2", "Tema 2.1")] == {"multichoice": 1}
    assert report.sin_categoria_por_tipo == {}
    assert report.omitidas == []


def test_preview_incluye_listado_de_preguntas_por_categoria():
    """RED→GREEN: cada categoría trae el detalle (enunciado, tipo) de sus preguntas,
    no solo el conteo — necesario para desplegar el detalle en el preview."""
    report = preview_import_banco(XML_MIXTO)

    por_ruta = {tuple(c.ruta): c.preguntas for c in report.categorias}
    enunciados_u1 = {p.enunciado for p in por_ruta[("Unidad 1",)]}
    assert enunciados_u1 == {"Enunciado 1", "Enunciado 2"}
    enunciados_u2 = {p.enunciado for p in por_ruta[("Unidad 2", "Tema 2.1")]}
    assert enunciados_u2 == {"Enunciado 3"}


def test_preview_pregunta_sin_categoria():
    """TRIANGULATE: pregunta sin categoria_ruta va a sin_categoria_por_tipo."""
    report = preview_import_banco(XML_SIN_CATEGORIA)

    assert report.total_preguntas == 1
    assert report.categorias == []
    assert report.sin_categoria_por_tipo == {"multichoice": 1}
    assert [p.enunciado for p in report.sin_categoria_preguntas] == ["Sin categoria"]


def test_preview_omite_pregunta_invalida():
    """TRIANGULATE: multichoice con 0 correctas se reporta en omitidas, no cuenta en el total."""
    report = preview_import_banco(XML_CON_INVALIDA)

    assert report.total_preguntas == 0
    assert len(report.omitidas) == 1
    assert report.omitidas[0].motivo != ""
