"""Tests unitarios de calcular_score() — sin DB, sin red.

Verifica pesos por severidad, score cero, score maximo y severidades desconocidas.
L2.5: el score solo prioriza la revision humana, nunca sanciona.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.proctoring.scoring import PESOS_SEVERIDAD, calcular_score


@dataclass
class _FakeEvento:
    """Evento fake duck-typed para tests unitarios (sin DB)."""

    severidad: str


def test_score_cero_sin_eventos() -> None:
    """Score de lista vacia es 0."""
    assert calcular_score([]) == 0


def test_score_bajo() -> None:
    """Un evento 'bajo' → peso 5."""
    assert calcular_score([_FakeEvento("bajo")]) == 5


def test_score_medio() -> None:
    """Un evento 'medio' → peso 20."""
    assert calcular_score([_FakeEvento("medio")]) == 20


def test_score_alto() -> None:
    """Un evento 'alto' → peso 50."""
    assert calcular_score([_FakeEvento("alto")]) == 50


def test_score_critico() -> None:
    """Un evento 'critico' → peso 100."""
    assert calcular_score([_FakeEvento("critico")]) == 100


def test_score_suma_multiples() -> None:
    """Score de multiples eventos suma sus pesos."""
    eventos = [
        _FakeEvento("bajo"),    # 5
        _FakeEvento("medio"),   # 20
        _FakeEvento("alto"),    # 50
        _FakeEvento("critico"), # 100
    ]
    assert calcular_score(eventos) == 175


def test_score_severidad_desconocida_es_cero() -> None:
    """Severidad no mapeada no suma (evita error silencioso)."""
    assert calcular_score([_FakeEvento("ultra")]) == 0
    assert calcular_score([_FakeEvento("")]) == 0


def test_pesos_alineados_con_frontend() -> None:
    """Los pesos son exactamente los definidos en la spec (D5, riskWeights del frontend)."""
    assert PESOS_SEVERIDAD["bajo"] == 5
    assert PESOS_SEVERIDAD["medio"] == 20
    assert PESOS_SEVERIDAD["alto"] == 50
    assert PESOS_SEVERIDAD["critico"] == 100


def test_score_solo_criticos() -> None:
    """3 eventos criticos → 300."""
    eventos = [_FakeEvento("critico")] * 3
    assert calcular_score(eventos) == 300
