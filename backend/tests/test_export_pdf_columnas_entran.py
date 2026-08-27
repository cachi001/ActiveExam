"""Las columnas del PDF tienen que ENTRAR en la hoja, o se cortan sin avisar.

`tabla_a_pdf` dibuja cada celda con un ancho fijo en milímetros, una al lado de la
otra. Si la suma de los anchos supera el ancho útil de la página, las columnas que
sobran quedan fuera del papel: el PDF sale igual, sin error, y quien lo abre no
tiene forma de saber que le falta información.

Pasó al agregar Consentimiento, Biometría y "¿Puede rendir?" al export de
inscriptos: los anchos pasaron a sumar 295 mm contra 186 mm útiles de un A4
vertical, y el archivo se cortaba justo en las columnas nuevas. En el Excel se
veían; en el PDF, no.

Este test no mira el dibujo: compara la suma de anchos contra el ancho útil real
de la orientación con la que se genera cada export. Falla si alguien agrega una
columna que no entra.
"""

from __future__ import annotations

import pytest

from app.application.exam_content.export import (
    COLUMNAS_INSCRIPTOS,
    COLUMNAS_NOTAS,
    INSCRIPTOS_APAISADO,
    NOTAS_APAISADO,
    ancho_util_mm,
)


def _suma(columnas) -> int:
    return sum(c.ancho_pdf for c in columnas)


@pytest.mark.parametrize(
    "nombre,columnas,apaisado",
    [
        ("inscriptos", COLUMNAS_INSCRIPTOS, INSCRIPTOS_APAISADO),
        ("notas", COLUMNAS_NOTAS, NOTAS_APAISADO),
    ],
)
def test_las_columnas_entran_en_la_hoja(nombre, columnas, apaisado):
    util = ancho_util_mm(apaisado)
    total = _suma(columnas)
    assert total <= util, (
        f"El export de {nombre} suma {total} mm de columnas y en la hoja "
        f"{'apaisada' if apaisado else 'vertical'} entran {util} mm. "
        "Las columnas de la derecha se cortan sin aviso: achicá anchos o pasá "
        "el export a apaisado."
    )


def test_el_export_de_inscriptos_va_apaisado():
    """Con 8 columnas no entra en vertical: es una decisión, no un detalle."""
    assert INSCRIPTOS_APAISADO is True


def test_las_columnas_de_elegibilidad_siguen_estando():
    """Que entren no puede lograrse borrando justo lo que se agregó."""
    titulos = [c.titulo for c in COLUMNAS_INSCRIPTOS]
    assert "Consentimiento" in titulos
    assert "Biometría" in titulos
    assert "¿Puede rendir?" in titulos


def test_ancho_util_apaisado_es_mayor_que_vertical():
    assert ancho_util_mm(True) > ancho_util_mm(False)
