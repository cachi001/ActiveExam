"""Tests del consumo server-side de la config viva en el scoring (config-driven-scoring).

calcular_score acepta pesos VIVOS por tipo de evento (de evento_score_config via
ConfigService). Sin config -> fallback a los pesos hardcodeados por severidad
(red de seguridad de degradacion, RN-GLB-03). L2.5: el score prioriza, nunca sanciona.

Tests PUROS (sin DB): solo el algoritmo con weights inyectados.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.proctoring.scoring import calcular_score


@dataclass
class _Evento:
    severidad: str
    tipo: str = ""


def test_usa_pesos_vivos_por_tipo() -> None:
    """Con pesos_por_tipo, el score usa el peso editado, no el default por severidad."""
    eventos = [_Evento(severidad="alta", tipo="multiples_rostros")]
    # Peso vivo editado a 77 (distinto del default por severidad alta=45).
    score = calcular_score(eventos, pesos_por_tipo={"multiples_rostros": 77})
    assert score == 77


def test_fallback_a_severidad_sin_config() -> None:
    """Sin pesos_por_tipo (config ausente) usa la red de seguridad por severidad."""
    eventos = [_Evento(severidad="alta", tipo="multiples_rostros")]
    assert calcular_score(eventos) == 45  # default por severidad alta (C-15: alta=45)


def test_tipo_no_en_config_cae_a_severidad() -> None:
    """Un tipo no presente en los pesos vivos cae al peso por severidad."""
    eventos = [_Evento(severidad="media", tipo="tipo_desconocido")]
    score = calcular_score(eventos, pesos_por_tipo={"otro_tipo": 99})
    assert score == 20  # severidad media default


def test_suma_mixta_vivos_y_fallback() -> None:
    eventos = [
        _Evento(severidad="alta", tipo="multiples_rostros"),  # vivo 77
        _Evento(severidad="media", tipo="cambio_pestana"),    # fallback severidad 20
    ]
    score = calcular_score(eventos, pesos_por_tipo={"multiples_rostros": 77})
    assert score == 97
