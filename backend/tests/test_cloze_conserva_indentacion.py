"""El código de las preguntas de completar tiene que conservar su sangría.

Caso real (29/8/2026, examen "Parcial U1-U3 — completar código"): las 10 preguntas
llegaban al alumno con el código Python pegado al margen izquierdo:

    def agregar(elemento, destino=[▼]):
    if [▼]:
    destino = []
    [▼]
    return destino

En Python la indentación ES sintaxis: define si `return destino` está adentro o
afuera del `if`. Sin ella, varias de estas preguntas son directamente irresolubles
— y son de completar código, así que la estructura es justo lo que se evalúa.

La causa está en `_strip_html`, que colapsaba TODO el espacio horizontal:

    re.sub(r"[ \\t]+", " ", text)         # 4 espacios → 1
    re.sub(r"[ \\t]*\\n[ \\t]*", "\\n", text)  # borra la sangría de cada renglón

Esas dos líneas existen por una razón válida (el HTML de Moodle viene con saltos y
espacios de formato que ensucian el enunciado). Lo que hay que conservar es el
espacio del COMIENZO de cada línea, que es el único que significa algo.

Tests de dominio sobre la función pura, sin DB.
"""

from __future__ import annotations

from app.application.exam_content.moodle_parser import _strip_html


class TestSangriaDelCodigo:
    def test_conserva_la_sangria_de_cada_linea(self) -> None:
        html = "def f():<br>    if x:<br>        return 1"
        assert _strip_html(html) == "def f():\n    if x:\n        return 1"

    def test_distingue_dos_niveles_de_anidamiento(self) -> None:
        # Lo que se evalúa en estas preguntas: si el return está dentro del if.
        # Con <br>: un salto por línea. (Con <p>…</p>, el cierre y la apertura
        # aportan un salto cada uno; eso es comportamiento de siempre, no se toca.)
        html = "if a:<br>    if b:<br>        return 1<br>    return 2"
        assert _strip_html(html) == "if a:\n    if b:\n        return 1\n    return 2"

    def test_conserva_la_sangria_hecha_con_tabs(self) -> None:
        html = "def f():<br>\tif x:<br>\t\treturn 1"
        assert _strip_html(html) == "def f():\n\tif x:\n\t\treturn 1"

    def test_no_deja_sangria_en_la_primera_linea(self) -> None:
        # El bloque entero suele venir con margen del HTML; el enunciado no arranca
        # indentado. Solo importa la sangría RELATIVA entre líneas.
        assert _strip_html("  Consigna:<br>  def f():") == "Consigna:\ndef f():"


class TestLoQueSeSIGUELIMPIANDO:
    """La limpieza que motivó esas dos líneas no se pierde."""

    def test_colapsa_espacios_repetidos_dentro_de_la_linea(self) -> None:
        # Espaciado de formato del HTML en medio de una oración: sigue colapsando.
        assert _strip_html("<p>hola     mundo</p>") == "hola mundo"

    def test_saca_el_espacio_del_final_de_la_linea(self) -> None:
        assert _strip_html("hola   <br>mundo") == "hola\nmundo"

    def test_colapsa_lineas_en_blanco_de_mas(self) -> None:
        assert _strip_html("<p>a</p><br><br><br><br><p>b</p>") == "a\n\nb"

    def test_sigue_quitando_los_tags(self) -> None:
        assert _strip_html("<p><strong>hola</strong> <em>mundo</em></p>") == "hola mundo"

    def test_sigue_decodificando_entidades(self) -> None:
        assert _strip_html("<p>a &lt;= b &amp;&amp; c</p>") == "a <= b && c"

    def test_no_deja_espacio_al_principio_ni_al_final_del_texto(self) -> None:
        assert _strip_html("<p>   hola   </p>") == "hola"


class TestPlaceholdersCloze:
    """Los campos cloze tienen que sobrevivir intactos (usan {} y [[ ]], no <>)."""

    def test_el_placeholder_cloze_no_se_toca(self) -> None:
        html = "<p>destino = {1:MULTICHOICE_S:=None#Es el centinela.~[]#No.}</p>"
        assert _strip_html(html) == "destino = {1:MULTICHOICE_S:=None#Es el centinela.~[]#No.}"

    def test_placeholder_cloze_indentado_conserva_su_sangria(self) -> None:
        html = "def f():<br>    return {1:SHORTANSWER:=x}"
        assert _strip_html(html) == "def f():\n    return {1:SHORTANSWER:=x}"
