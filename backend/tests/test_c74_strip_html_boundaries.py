"""C-74: _strip_html no debe pegar palabras al borrar tags de bloque.

Bug real (reportado en vivo, campus real): una pregunta cloze con
``<p>{blank1} = input("...")<br>{blank2} = input("...")</p>`` perdía el <br>
sin dejar separador -> el texto quedaba `")elegir` pegado, sin espacio entre
el cierre de comillas de un blank y el próximo control. Pasa con CUALQUIER
tag de bloque (<br>, </p>, </div>, </li>, <td>/<th>) cuando el HTML fuente no
trae un salto de línea literal entre tags (HTML minificado).

_strip_html es función interna (import directo del módulo, no hay symbol
público) — se prueba vía el símbolo `_strip_html` reexportado para test.
"""

from __future__ import annotations

from app.application.exam_content.moodle_parser import _strip_html


def test_br_sin_salto_no_pega_palabras():
    """RED→GREEN: <br> sin whitespace alrededor debe separar, no pegar."""
    html = '{1} = input("Por favor, ingrese su nombre: ")<br>{2} = input("Por favor, ingrese su apellido: ")'
    resultado = _strip_html(html)
    assert '")elegir' not in resultado.replace(' ', '')  # placeholder de referencia, no debe pegarse
    assert '"){2}' not in resultado  # el patrón crudo tampoco debe quedar pegado
    assert resultado.count('\n') >= 1 or resultado.count('  ') == 0 and '") {2}' in resultado or '")\n{2}' in resultado


def test_parrafos_sin_salto_literal_no_se_pegan():
    """TRIANGULATE: <p>A</p><p>B</p> sin newline en la fuente no debe dar 'AB'."""
    html = "<p>Primera oracion.</p><p>Segunda oracion.</p>"
    resultado = _strip_html(html)
    assert "oracion.Segunda" not in resultado
    assert "Primera oracion." in resultado
    assert "Segunda oracion." in resultado


def test_celdas_de_tabla_no_se_pegan():
    """TRIANGULATE: <td>A</td><td>B</td> sin espacio en la fuente no debe dar 'AB'."""
    html = "<tr><td>Micaela</td><td>Hoffman</td></tr>"
    resultado = _strip_html(html)
    assert "MicaelaHoffman" not in resultado
    assert "Micaela" in resultado
    assert "Hoffman" in resultado


def test_caso_real_del_bug_reportado():
    """TRIANGULATE: reproduce el HTML real de campustest que generó el bug."""
    html = (
        '<div>​</div>\n'
        '<div>\n'
        '<p>{1:MULTICHOICE_S:=nombre~apellido~nombre_completo} = input("Por favor, ingrese su nombre: ")'
        '<br>{1:MULTICHOICE_S:=apellido~nombre~nombre_completo} = input("Por favor, ingrese su apellido: ")</p>\n'
        '<p>{1:MULTICHOICE_S:=nombre_completo~nombre~apellido} = nombre + " " + apellido</p>\n'
        '</div>\n'
        '<p dir="ltr">print(nombre_completo)</p>'
    )
    resultado = _strip_html(html)
    # El cierre de un blank nunca debe tocar la apertura del siguiente sin separador.
    assert '")​{1' not in resultado
    assert '"){1' not in resultado
    assert 'apellido: ")print' not in resultado


def test_no_agrega_separadores_espurios_en_texto_simple():
    """Control: texto sin tags de bloque no gana saltos de línea de más."""
    html = "Enunciado simple sin nada raro."
    assert _strip_html(html) == "Enunciado simple sin nada raro."


def test_inline_tags_no_agregan_separador():
    """Control: <strong>/<em> no deben insertar espacio dentro de una palabra."""
    html = "<strong>Hola</strong> mundo"
    resultado = _strip_html(html)
    assert resultado == "Hola mundo"


def test_entidades_html_se_decodifican():
    """RED→GREEN: &lt;= debe convertirse en <=, no quedar literal en el enunciado.

    Bug real visto en campustest: una comparación `rango_minimo <= x` exportada
    por Moodle como `rango_minimo &lt;= x` quedaba literalmente como
    "rango_minimo &lt;= x" en el enunciado renderizado al alumno.
    """
    texto = "dentro_rango = (rango_minimo &lt;= x and x &lt;= rango_maximo)"
    resultado = _strip_html(texto)
    assert "&lt;" not in resultado
    assert "rango_minimo <= x" in resultado


def test_entidad_no_se_confunde_con_tag_tras_decodificar():
    """Control: decodificar &lt;=&gt; DESPUÉS de quitar tags reales no debe
    hacer que el resultado sea tratado como un tag y perder contenido."""
    texto = "<p>a &lt;= b</p><p>siguiente linea</p>"
    resultado = _strip_html(texto)
    assert "a <= b" in resultado
    assert "siguiente linea" in resultado


def test_lineas_de_solo_nbsp_colapsan_como_linea_en_blanco():
    """RED→GREEN: una línea con \xa0 (nbsp ya decodificado, tal cual queda tras
    el unescape de &nbsp; que Moodle usa como línea "vacía" de separación) no
    debe generar un salto visual gigante — debe colapsar igual que una línea
    realmente vacía. Caso real de campustest: '\xa0\n\n\xa0\n\n' entre el
    enunciado y el código a completar."""
    texto = "<p>Enunciado.</p>\n<p>\xa0</p>\n<p>\xa0</p>\n<p>Complete el código:</p>"
    resultado = _strip_html(texto)
    assert "\n\n\n" not in resultado
    assert "Enunciado." in resultado
    assert "Complete el código:" in resultado


def test_code_tag_se_preserva_como_marcador():
    """RED->GREEN: <code>...</code> debe sobrevivir como tramo marcado, no
    perderse junto con el resto de los tags -- es la senal que Moodle usa
    para resaltar codigo (ver captura real de campustest, autoevaluacion_
    unidad1_5: <p><code>a = 1</code><br><code>b = 2</code></p>)."""
    from app.application.exam_content.moodle_parser import (
        CODE_MARCA_INICIO,
        CODE_MARCA_FIN,
        _strip_html,
    )

    html_src = '<p><code>a = 1</code><br><code>b = 2</code></p>'
    resultado = _strip_html(html_src)
    assert resultado == f"{CODE_MARCA_INICIO}a = 1{CODE_MARCA_FIN}\n{CODE_MARCA_INICIO}b = 2{CODE_MARCA_FIN}"


def test_code_tag_no_afecta_texto_sin_code():
    """Control: preguntas sin <code> (la mayoria del banco real) siguen
    dando exactamente el mismo resultado que antes de este cambio."""
    from app.application.exam_content.moodle_parser import _strip_html

    html_src = '<p>dentro_rango = (rango_minimo &lt;= x)</p>'
    resultado = _strip_html(html_src)
    assert resultado == "dentro_rango = (rango_minimo <= x)"


def test_code_tag_con_atributos_tambien_se_detecta():
    """TRIANGULATE: <code style="..."> (con atributos, visto en el XML real
    de campustest) debe detectarse igual que <code> a secas."""
    from app.application.exam_content.moodle_parser import (
        CODE_MARCA_INICIO,
        CODE_MARCA_FIN,
        _strip_html,
    )

    html_src = '<code data-start="281" data-end="287">print(x)</code>'
    resultado = _strip_html(html_src)
    assert resultado == f"{CODE_MARCA_INICIO}print(x){CODE_MARCA_FIN}"
