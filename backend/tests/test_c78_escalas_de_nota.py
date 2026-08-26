"""c-78 — La nota da lo mismo con escala 100/60 y con 10/6 (pedido del dueño).

    "revisa si como se calcula la nota esta correcto segun si pongo de 100 maxima
     calificacion y para aprobar 60 o si yo pongo 10 como maxima calificacion y
     para aprobar 6"

Son la MISMA exigencia expresada en dos escalas: 6 de 10 y 60 de 100 son el mismo
60%. Un alumno con las mismas respuestas tiene que aprobar o desaprobar igual en
las dos, y en el borde (justo el mínimo) tiene que aprobar en las dos.

Acá se verifica la proporción y el redondeo, que es donde estas cosas se rompen:
con 7 de 12 preguntas, 100/60 da 58,33 (desaprueba) y 10/6 da 5,83 (desaprueba
también). Si una redondeara para arriba y la otra no, el mismo examen aprobaría
en una escala y no en la otra.
"""

from __future__ import annotations

import pytest

from app.application.moodle.grade_calculator import nota_desde_correctas


def _aprueba(correctas: int, total: int, maxima: float, minima: float) -> bool:
    return nota_desde_correctas(correctas, total, maxima) >= minima


@pytest.mark.parametrize("correctas, total", [(6, 10), (7, 10), (10, 10), (0, 10)])
def test_las_dos_escalas_dan_el_mismo_veredicto(correctas, total):
    en_100 = _aprueba(correctas, total, 100.0, 60.0)
    en_10 = _aprueba(correctas, total, 10.0, 6.0)

    assert en_100 == en_10, (
        f"{correctas}/{total}: aprueba en 100/60 = {en_100}, en 10/6 = {en_10}"
    )


def test_el_borde_exacto_aprueba_en_las_dos():
    """6 de 10 es justo el mínimo: tiene que aprobar, no quedar afuera por un
    decimal."""
    assert nota_desde_correctas(6, 10, 100.0) == 60.0
    assert nota_desde_correctas(6, 10, 10.0) == 6.0
    assert _aprueba(6, 10, 100.0, 60.0) is True
    assert _aprueba(6, 10, 10.0, 6.0) is True


def test_justo_abajo_del_borde_desaprueba_en_las_dos():
    assert _aprueba(5, 10, 100.0, 60.0) is False
    assert _aprueba(5, 10, 10.0, 6.0) is False


def test_un_caso_con_decimales_feos_no_cambia_de_veredicto():
    """7 de 12 = 58,33%: desaprueba en las dos escalas."""
    assert nota_desde_correctas(7, 12, 100.0) == 58.33
    assert nota_desde_correctas(7, 12, 10.0) == 5.83
    assert _aprueba(7, 12, 100.0, 60.0) is False
    assert _aprueba(7, 12, 10.0, 6.0) is False


def test_todas_bien_da_el_maximo_exacto():
    assert nota_desde_correctas(10, 10, 100.0) == 100.0
    assert nota_desde_correctas(10, 10, 10.0) == 10.0


def test_ninguna_bien_da_cero():
    assert nota_desde_correctas(0, 10, 100.0) == 0.0
    assert nota_desde_correctas(0, 10, 10.0) == 0.0


def test_un_examen_sin_preguntas_no_divide_por_cero():
    """Pasa de verdad: un examen en borrador o mal armado. Tiene que dar 0, no
    reventar en medio de la entrega del alumno."""
    assert nota_desde_correctas(0, 0, 100.0) == 0.0


def test_el_redondeo_es_medio_para_arriba():
    """1 de 3 = 33,333 → 33,33. 2 de 3 = 66,666 → 66,67."""
    assert nota_desde_correctas(1, 3, 100.0) == 33.33
    assert nota_desde_correctas(2, 3, 100.0) == 66.67
