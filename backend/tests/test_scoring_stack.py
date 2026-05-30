"""Tests del scoring que requieren el stack (C-13, @requires_stack).

Necesitan TimescaleDB con la migracion 0004 (continuous aggregate de score) y/o
Prometheus levantados; se saltan salvo RUN_STACK_TESTS=1 (conftest).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requires_stack


def test_continuous_aggregate_de_score_refresca_al_minuto() -> None:
    """El continuous aggregate cagg_score_ponderado_min (0004) materializa el score
    ponderado por sesion al minuto y la lectura sale del agregado (CQRS-lite).

    Requiere TimescaleDB con 0004 aplicada e ingesta de eventos."""
    pytest.skip("requiere TimescaleDB con 0004 (RUN_STACK_TESTS=1)")


def test_lectura_de_score_desde_el_agregado_no_recorre_la_hypertable() -> None:
    """La lectura del score en vivo consulta cagg_score_ponderado_min, no la
    hypertable cruda (DD-05, CQRS-lite)."""
    pytest.skip("requiere TimescaleDB con 0004 (RUN_STACK_TESTS=1)")


def test_distribucion_de_score_visible_en_prometheus() -> None:
    """La distribucion de score se expone como metrica de negocio para el monitoreo
    del backlog de revision (`14`)."""
    pytest.skip("requiere Prometheus + ingesta (RUN_STACK_TESTS=1)")
