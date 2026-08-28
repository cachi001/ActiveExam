"""Sortear N preguntas de TODO el banco, sin repartir por categoría.

El selector obligaba a ir categoría por categoría. Para el caso más común —
"quiero un examen de 10 preguntas de las 38 que tengo"— eso es trabajo de más, y
peor: repartir a mano por categoría reduce la variedad sin que se note. Pedir 3
de una categoría que tiene 3 no sortea nada, y el docente se entera leyendo la
letra chica.

Un tramo SIN categoría y con la descendencia incluida significa "todo el banco":
`categoria_id = NULL` sola sigue siendo "sin clasificar", como antes.
"""

from __future__ import annotations

from app.application.exam_content.sorteo_por_intento import categorias_admitidas


def test_sin_categoria_y_con_descendencia_es_todo_el_banco():
    admitidas = categorias_admitidas(
        categoria_id=None, incluir_subcategorias=True, hijos={}
    )
    assert admitidas is None, "None = sin filtro de categoría: entra todo"


def test_sin_categoria_y_sin_descendencia_sigue_siendo_sin_clasificar():
    """El comportamiento de siempre: las preguntas que no tienen categoría."""
    admitidas = categorias_admitidas(
        categoria_id=None, incluir_subcategorias=False, hijos={}
    )
    assert admitidas == {None}


def test_una_categoria_sin_descendencia_es_solo_ella():
    admitidas = categorias_admitidas(
        categoria_id="cat-1", incluir_subcategorias=False, hijos={"cat-1": ["cat-2"]}
    )
    assert admitidas == {"cat-1"}


def test_una_categoria_con_descendencia_baja_a_los_hijos():
    admitidas = categorias_admitidas(
        categoria_id="cat-1",
        incluir_subcategorias=True,
        hijos={"cat-1": ["cat-2"], "cat-2": ["cat-3"]},
    )
    assert admitidas == {"cat-1", "cat-2", "cat-3"}
