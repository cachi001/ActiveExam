"""registrar_seguro NO debe tragar fallos en silencio (cadena de custodia).

Es best-effort (no rompe la operación auditada), PERO un fallo de auditoría es un
evento serio en un sistema de proctoring: si no se loguea, se pierden entradas de
la cadena de custodia sin que nadie se entere. Este test fija el contrato: ante un
fallo, registrar_seguro devuelve False Y deja un registro de log de nivel ERROR.
"""

from __future__ import annotations

import logging

import pytest

from app.application.audit.service import registrar_seguro


class _FactoryQueRevienta:
    """session_factory() que falla al abrir la sesión (simula fallo transitorio)."""

    def __call__(self):
        raise RuntimeError("conexión caída")


@pytest.mark.asyncio
async def test_registrar_seguro_loguea_el_fallo(caplog):
    with caplog.at_level(logging.ERROR):
        ok = await registrar_seguro(
            _FactoryQueRevienta(),
            actor="admin@x",
            accion="materia.delete",
            proposito="Eliminó la materia X",
        )

    assert ok is False  # best-effort: no propaga
    # Pero NO es silencioso: quedó un log de ERROR con la acción y el actor.
    errores = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errores, "el fallo de auditoría debe loguearse, no tragarse en silencio"
    mensaje = " ".join(r.getMessage() for r in errores)
    assert "materia.delete" in mensaje
