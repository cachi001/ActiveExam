"""Tests unitarios de nivel_riesgo() — sin DB, sin red (C-76 tarea 17).

Espeja nivelRiesgo() del frontend (proctoring/helpers.ts): bajo/medio/alto
segun el score y el umbral_alto VIVO (umbral_cola_revision).
"""

from __future__ import annotations

from app.application.proctoring.scoring import SCORE_UMBRAL_MEDIO, nivel_riesgo


def test_score_bajo_umbral_medio_es_bajo() -> None:
    assert nivel_riesgo(0, umbral_alto=70) == "bajo"
    assert nivel_riesgo(SCORE_UMBRAL_MEDIO - 1, umbral_alto=70) == "bajo"


def test_score_en_umbral_medio_es_medio() -> None:
    assert nivel_riesgo(SCORE_UMBRAL_MEDIO, umbral_alto=70) == "medio"
    assert nivel_riesgo(69, umbral_alto=70) == "medio"


def test_score_en_umbral_alto_es_alto() -> None:
    assert nivel_riesgo(70, umbral_alto=70) == "alto"
    assert nivel_riesgo(100, umbral_alto=70) == "alto"


def test_umbral_alto_configurable_desplaza_el_corte() -> None:
    """Un umbral_alto distinto (config viva, no hardcodeado) desplaza el corte."""
    assert nivel_riesgo(50, umbral_alto=50) == "alto"
    assert nivel_riesgo(49, umbral_alto=50) == "medio"
