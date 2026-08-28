"""El que no rindió aparece en el listado, desaprobado y con el motivo.

Antes no aparecía: sin sesión de proctoring no había fila, así que el docente
veía 30 filas de un curso de 40 y no tenía cómo saber quiénes faltaban. La nota
de quien no se presentó es 0 y el resultado es desaprobado — pero con el motivo
a la vista, porque no es lo mismo que desaprobar habiendo rendido.
"""

from __future__ import annotations

from app.application.moodle.resultados_query import fila_de_ausente
from app.domain.exam_content.resultado_nota import ResultadoNota


def test_el_ausente_sale_desaprobado_con_cero():
    fila = fila_de_ausente(
        usuario_id="u-1",
        idnumber="EST-001",
        email="est1@uni.edu",
        nombre="Pérez, Ana",
    )
    assert fila.resultado == ResultadoNota.DESAPROBADO.value
    assert fila.nota == 0.0
    assert fila.nota_efectiva == 0.0


def test_dice_que_no_rindio():
    """Sin el motivo, un 0 se lee igual que el de alguien que rindió y no supo
    nada. Son dos situaciones distintas y se reclaman distinto."""
    fila = fila_de_ausente(
        usuario_id="u-1", idnumber="EST-001", email="est1@uni.edu", nombre=None
    )
    assert "no_rindio" in fila.retenciones


def test_no_tiene_sesion_asi_que_no_se_puede_operar_sobre_el():
    """No hay nada que publicar ni que marcar: nunca rindió. El `session_id`
    vacío es lo que la pantalla usa para no ofrecer acciones imposibles."""
    fila = fila_de_ausente(
        usuario_id="u-1", idnumber="EST-001", email="est1@uni.edu", nombre=None
    )
    assert fila.session_id == ""


def test_sin_nombre_cargado_cae_al_legajo():
    fila = fila_de_ausente(
        usuario_id="u-1", idnumber="EST-001", email="est1@uni.edu", nombre=None
    )
    assert fila.alumno_nombre is None
    assert fila.alumno_idnumber == "EST-001"


# ---------------------------------------------------------------------------
# El ausente se calcula contra TODAS las sesiones del examen, no contra la
# página que se está mostrando. Mirando sólo la página, un alumno que rindió y
# quedó en la página 2 aparecía ADEMÁS como ausente en la página 1: la misma
# persona dos veces, una con su nota y otra con 0. Encontrado en pantalla el
# 28/8/2026 con `page_size=5`.
# ---------------------------------------------------------------------------

import inspect

from app.application.moodle.resultados_query import _ausentes_del_examen


def test_los_ausentes_no_se_calculan_contra_una_pagina():
    """La firma no recibe la página: si alguien vuelve a pasarle un subconjunto,
    el duplicado vuelve."""
    params = set(inspect.signature(_ausentes_del_examen).parameters)
    assert params == {"db", "examen_id"}


def test_pregunta_por_todas_las_sesiones_del_examen():
    fuente = inspect.getsource(_ausentes_del_examen)
    assert "examen_contenido_id == examen_id" in fuente
    assert "rindieron" in fuente
