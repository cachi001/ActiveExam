"""Tests de la validacion PURA de parametros de examen (C-07 D4, RN-EX-01).

Verifica que la capa de dominio rechaza configuraciones invalidas (ventana
incoherente, detector desconocido, umbral fuera de rango, retencion invalida) con
``InvalidExamConfigError`` ANTES de persistir, y acepta una config valida.

Dominio puro -> sin DB ni libs externas.
"""

from __future__ import annotations

import pytest

from app.domain.exam_config.errors import InvalidExamConfigError
from app.domain.exam_config.validation import validar_config_examen

_OK = dict(
    inicio="2026-06-01T09:00:00Z",
    fin="2026-06-01T11:00:00Z",
    umbral_score=0.7,
    detectores=("face_detection", "face_mesh"),
    umbrales_detector={"face_detection": 0.5},
    politica_retencion="estandar",
)


def test_config_valida_no_levanta() -> None:
    validar_config_examen(**_OK)


def test_ventana_incoherente_rechazada() -> None:
    bad = {**_OK, "fin": "2026-06-01T08:00:00Z"}  # fin <= inicio
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    assert "ventana" in ei.value.detalles


def test_detector_desconocido_rechazado() -> None:
    bad = {**_OK, "detectores": ("face_detection", "telepatia")}
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    assert "detectores" in ei.value.detalles


def test_umbral_fuera_de_rango_rechazado() -> None:
    bad = {**_OK, "umbral_score": 1.5}
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    assert "umbral_score" in ei.value.detalles


def test_retencion_invalida_rechazada() -> None:
    bad = {**_OK, "politica_retencion": "para_siempre"}
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    assert "retencion" in ei.value.detalles


def test_umbral_detector_fuera_de_rango_rechazado() -> None:
    bad = {**_OK, "umbrales_detector": {"face_detection": 2.0}}
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    assert any(k.startswith("umbrales.") for k in ei.value.detalles)


def test_errores_se_agregan() -> None:
    bad = {
        **_OK,
        "fin": "2026-06-01T08:00:00Z",
        "umbral_score": 9.0,
        "detectores": ("x",),
    }
    with pytest.raises(InvalidExamConfigError) as ei:
        validar_config_examen(**bad)
    # Reporta TODOS los problemas, no solo el primero (D4).
    assert {"ventana", "umbral_score", "detectores"} <= set(ei.value.detalles)
