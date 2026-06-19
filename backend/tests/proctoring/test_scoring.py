"""Tests unitarios de calcular_score() — sin DB, sin red.

Verifica pesos por severidad (fallback, RN-GLB-03), score cero, suma de
multiples eventos y severidades desconocidas. L2.5: el score solo prioriza la
revision humana, nunca sanciona.

Las severidades canonicas son ``baja``, ``media``, ``alta``, ``critica``
(alineadas con ``evento_score_config`` y ``app/domain/scoring/risk_score.py``);
``baseline`` no es un evento y no suma. Los pesos del fallback son el centro de
los rangos institucionales (SEVERITY_RANGES).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.proctoring.scoring import PESOS_SEVERIDAD, calcular_score


@dataclass
class _FakeEvento:
    """Evento fake duck-typed para tests unitarios (sin DB)."""

    severidad: str
    tipo: str = ""


def test_score_cero_sin_eventos() -> None:
    """Score de lista vacia es 0."""
    assert calcular_score([]) == 0


def test_score_baja() -> None:
    """Un evento 'baja' → peso 5 (fallback, centro del rango [1-10])."""
    assert calcular_score([_FakeEvento("baja")]) == 5


def test_score_media() -> None:
    """Un evento 'media' → peso 20 (fallback, centro del rango [11-30])."""
    assert calcular_score([_FakeEvento("media")]) == 20


def test_score_alta() -> None:
    """Un evento 'alta' → peso 45 (fallback, centro del rango [31-60])."""
    assert calcular_score([_FakeEvento("alta")]) == 45


def test_score_critica() -> None:
    """Un evento 'critica' → peso 80 (fallback, centro del rango [61-100])."""
    assert calcular_score([_FakeEvento("critica")]) == 80


def test_score_suma_multiples() -> None:
    """Score de multiples eventos suma sus pesos."""
    eventos = [
        _FakeEvento("baja"),     # 5
        _FakeEvento("media"),    # 20
        _FakeEvento("alta"),     # 45
        _FakeEvento("critica"),  # 80
    ]
    assert calcular_score(eventos) == 150


def test_score_baseline_no_suma() -> None:
    """baseline no es un evento (piso 0 del score)."""
    assert calcular_score([_FakeEvento("baseline")]) == 0


def test_score_severidad_desconocida_es_cero() -> None:
    """Severidad no mapeada no suma (evita error silencioso)."""
    assert calcular_score([_FakeEvento("ultra")]) == 0
    assert calcular_score([_FakeEvento("")]) == 0


def test_pesos_fallback_alineados_con_rangos_institucionales() -> None:
    """El fallback por severidad debe estar dentro del rango institucional
    (SEVERITY_RANGES) de la severidad correspondiente, idealmente en el centro."""
    assert 1 <= PESOS_SEVERIDAD["baja"] <= 10
    assert 11 <= PESOS_SEVERIDAD["media"] <= 30
    assert 31 <= PESOS_SEVERIDAD["alta"] <= 60
    assert 61 <= PESOS_SEVERIDAD["critica"] <= 100


def test_score_solo_criticas() -> None:
    """3 eventos criticos → 240 (3 * 80)."""
    eventos = [_FakeEvento("critica")] * 3
    assert calcular_score(eventos) == 240
