"""Tests de la comparacion 1:1 por distancia coseno (C-09, logica pura).

Sin DB ni framework: aritmetica del dominio (RN-BIO-01/03). El umbral conservador
y la decision de match/no-match se ejercen con vectores conocidos.
"""

from __future__ import annotations

import math

import pytest

from app.domain.biometrics.matching import (
    UMBRAL_COSENO_DEFECTO,
    EmbeddingInvalidoError,
    comparar_identidad,
    distancia_coseno,
)


def test_distancia_de_vectores_identicos_es_cero() -> None:
    assert distancia_coseno([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)


def test_distancia_de_vectores_ortogonales_es_uno() -> None:
    assert distancia_coseno([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


def test_distancia_de_vectores_opuestos_es_dos() -> None:
    assert distancia_coseno([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)


def test_distancia_es_invariante_a_la_escala() -> None:
    # cos es invariante a la magnitud: escalar un vector no cambia la distancia.
    d1 = distancia_coseno([1.0, 1.0], [2.0, 0.0])
    d2 = distancia_coseno([10.0, 10.0], [2.0, 0.0])
    assert d1 == pytest.approx(d2)


def test_vectores_vacios_o_dim_distinta_o_norma_cero_levantan() -> None:
    with pytest.raises(EmbeddingInvalidoError):
        distancia_coseno([], [1.0])
    with pytest.raises(EmbeddingInvalidoError):
        distancia_coseno([1.0, 2.0], [1.0])
    with pytest.raises(EmbeddingInvalidoError):
        distancia_coseno([0.0, 0.0], [1.0, 1.0])


def test_match_cuando_distancia_bajo_umbral() -> None:
    # Vectores casi identicos -> distancia chica -> match.
    res = comparar_identidad([1.0, 0.0, 0.0], [0.999, 0.01, 0.0])
    assert res.distancia < UMBRAL_COSENO_DEFECTO
    assert res.es_match is True


def test_no_match_cuando_distancia_sobre_umbral() -> None:
    res = comparar_identidad([1.0, 0.0], [0.0, 1.0])  # ortogonales -> 1.0
    assert res.distancia >= UMBRAL_COSENO_DEFECTO
    assert res.es_match is False


def test_umbral_es_estricto_conservador() -> None:
    # En el umbral EXACTO no es match (estricto, RN-BIO-03 conservador). Tomamos
    # la distancia real de un par y la usamos como umbral: distancia == umbral.
    a = [1.0, 0.0]
    b = [math.cos(math.pi / 3), math.sin(math.pi / 3)]  # 60 grados
    distancia = comparar_identidad(a, b, umbral=1.0).distancia
    res = comparar_identidad(a, b, umbral=distancia)
    assert res.distancia == distancia
    assert res.es_match is False  # distancia == umbral NO es match (estricto)


def test_umbral_no_positivo_es_invalido() -> None:
    with pytest.raises(EmbeddingInvalidoError):
        comparar_identidad([1.0], [1.0], umbral=0.0)
