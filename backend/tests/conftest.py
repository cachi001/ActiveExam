"""Configuracion compartida de pytest.

Registra el marker ``requires_stack`` para los tests que necesitan el stack de
Docker Compose levantado (DB/storage/IdP). Esos tests se SALTAN automaticamente
salvo que ``RUN_STACK_TESTS=1`` este en el entorno, para que la suite unitaria
corra sin servicios externos.
"""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_stack: el test necesita el stack de Docker Compose levantado "
        "(DB/storage/IdP). Se salta salvo RUN_STACK_TESTS=1.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get("RUN_STACK_TESTS") == "1":
        return
    skip = pytest.mark.skip(
        reason="Requiere el stack levantado. Exporta RUN_STACK_TESTS=1 con el "
        "compose arriba para ejecutarlo."
    )
    for item in items:
        if "requires_stack" in item.keywords:
            item.add_marker(skip)
