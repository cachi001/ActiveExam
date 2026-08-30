"""Bandas de score alineadas al umbral de revisión (puras, sin DB).

ACTUALIZADO el 29/8/2026: las bandas usan el MISMO corte medio que el filtro
"nivel de riesgo" del Registro de sesiones (30). Antes tenían cortes propios
(25 y 50) y un score de 28 salía "bajo" en el filtro pero caía en la banda
"25-49" de la rosca: dos criterios para lo mismo.

BUG original que clavan estos tests: las bandas eran fijas (0-24 / 25-49 / 50-69 / 70-100)
mientras ``umbral_cola_revision`` es configurable (piso de producto 70, slider
hasta 90). Con umbral 80, una sesión de score 75 caía en la banda "70-100" —la
que la UI pinta como banda de riesgo— sin estar en riesgo, y el frontend marcaba
la banda con ``limite_inferior >= umbral`` (70 >= 80 = False), así que NINGUNA
banda quedaba señalada como riesgo mientras la tarjeta decía "1 en riesgo".

Contrato: la ÚLTIMA banda arranca EXACTAMENTE en el umbral. Así "estar en la
última banda" y "priorizar revisión humana" son la misma cosa, por construcción.

L2.5: la banda PRIORIZA la revisión humana; no es un veredicto (RN-SC-01).
"""

from __future__ import annotations

from app.application.stats.resumen_service import banda_de_score, bandas_de_score


def test_umbral_70_conserva_las_bandas_historicas() -> None:
    """Con el umbral por defecto las bandas son las de siempre (sin churn visual)."""
    assert bandas_de_score(70) == ["0-29", "30-69", "70-100"]


def test_umbral_80_estira_la_banda_previa_y_la_de_riesgo_arranca_en_80() -> None:
    """La banda de riesgo empieza en el umbral; la anterior se estira hasta 79."""
    assert bandas_de_score(80) == ["0-29", "30-79", "80-100"]


def test_umbral_90_idem() -> None:
    assert bandas_de_score(90) == ["0-29", "30-89", "90-100"]


def test_umbral_bajo_no_genera_bandas_vacias_ni_invertidas() -> None:
    """Umbral por debajo de los cortes fijos: se descartan los cortes que no aplican."""
    assert bandas_de_score(25) == ["0-24", "25-100"]  # umbral por debajo del corte medio
    assert bandas_de_score(40) == ["0-29", "30-39", "40-100"]


def test_score_cae_en_la_banda_correcta_con_umbral_80() -> None:
    """El caso del bug: 75 NO es riesgo con umbral 80; 85 sí, y caen en bandas distintas."""
    bandas = bandas_de_score(80)
    assert banda_de_score(75, bandas) == "30-79"
    assert banda_de_score(85, bandas) == "80-100"


def test_bordes_de_banda_son_inclusivos() -> None:
    bandas = bandas_de_score(70)
    assert banda_de_score(0, bandas) == "0-29"
    assert banda_de_score(29, bandas) == "0-29"
    assert banda_de_score(30, bandas) == "30-69"
    assert banda_de_score(69, bandas) == "30-69"
    assert banda_de_score(70, bandas) == "70-100"
    assert banda_de_score(100, bandas) == "70-100"


def test_la_ultima_banda_siempre_arranca_en_el_umbral() -> None:
    """Invariante del contrato, para todo umbral alcanzable por la UI (70..90)."""
    for umbral in range(70, 91):
        assert bandas_de_score(umbral)[-1] == f"{umbral}-100"
