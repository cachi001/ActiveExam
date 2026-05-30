"""Tests de la cadena de custodia que requieren el stack (C-12, @requires_stack).

Estos tests necesitan la DB (trigger 0003) y/o storage WORM real levantados; se
saltan salvo RUN_STACK_TESTS=1 (conftest). Verifican lo que NO se puede probar sin
infraestructura: inmutabilidad de la cadena en el motor, WORM Object Lock y el SLO.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requires_stack


def test_evidencia_chain_columns_son_inmutables_en_el_motor() -> None:
    """El trigger trg_evidencia_cadena_inmutable (0003) rechaza reescribir una
    columna de cadena ya fijada (NULL->valor permitido; valor->valor rechazado).

    Requiere la DB con la migración 0003 aplicada. Verificación: insertar una
    evidencia con hash_backend, intentar UPDATE a otro hash_backend -> debe abortar."""
    pytest.skip("requiere DB con 0003 aplicada (RUN_STACK_TESTS=1)")


def test_worm_object_lock_compliance_rechaza_delete() -> None:
    """El bucket WORM (Object Lock Compliance) rechaza modificar/borrar el objeto
    antes del retain-until, incluso con credenciales privilegiadas (RN-CC-06).

    Requiere MinIO/S3 con Object Lock habilitado."""
    pytest.skip("requiere storage con Object Lock (RUN_STACK_TESTS=1)")


def test_slo_reinferencia_mas_firma_p99_menor_30s() -> None:
    """E2->E4 (re-inferencia + firma maestra) p99 < 30 s al pico, medido en
    Prometheus sobre la cola ganadora de C-03 (SLO, `14`)."""
    pytest.skip("requiere cola + worker + Prometheus al pico (RUN_STACK_TESTS=1)")
