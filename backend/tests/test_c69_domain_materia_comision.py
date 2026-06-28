"""6.1 RED → 6.2 GREEN: tests de dominio — Materia y Comision (C-69, D11).

Corren SIN base de datos. Solo validan las reglas de dominio de las entidades.

Reglas (spec exam-content-model / D11):
- Materia: codigo (único a nivel DB) + nombre. Domain exige ambos no vacíos.
- Comision: codigo, nombre, FK obligatoria a materia (materia_id), período/anio opcional.
- Una comisión pertenece a EXACTAMENTE una materia → comisión sin materia es error de dominio.
"""

from __future__ import annotations

import pytest

from app.domain.exam_content.entities import Comision, Materia
from app.domain.exam_content.errors import (
    ComisionInvalidaError,
    MateriaInvalidaError,
)


# ---------------------------------------------------------------------------
# 6.1 RED — Materia
# ---------------------------------------------------------------------------


def test_materia_valida_no_lanza():
    m = Materia(codigo="ALG-101", nombre="Álgebra I")
    assert m.codigo == "ALG-101"
    assert m.nombre == "Álgebra I"
    assert m.id is None


def test_materia_sin_codigo_es_rechazada():
    with pytest.raises(MateriaInvalidaError):
        Materia(codigo="", nombre="Álgebra I")


def test_materia_sin_nombre_es_rechazada():
    with pytest.raises(MateriaInvalidaError):
        Materia(codigo="ALG-101", nombre="")


def test_materia_inmutable():
    m = Materia(codigo="ALG-101", nombre="Álgebra I")
    with pytest.raises((AttributeError, TypeError)):
        m.codigo = "OTRO"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6.1 RED — Comision
# ---------------------------------------------------------------------------


def test_comision_valida_no_lanza():
    c = Comision(
        codigo="C1",
        nombre="Comisión 1",
        materia_id="11111111-1111-1111-1111-111111111111",
    )
    assert c.codigo == "C1"
    assert c.materia_id == "11111111-1111-1111-1111-111111111111"
    assert c.periodo is None
    assert c.anio is None
    assert c.id is None


def test_comision_con_periodo_y_anio_opcionales():
    c = Comision(
        codigo="C1",
        nombre="Comisión 1",
        materia_id="m-1",
        periodo="1C",
        anio=2026,
    )
    assert c.periodo == "1C"
    assert c.anio == 2026


def test_comision_sin_materia_es_rechazada():
    """Una comisión pertenece a EXACTAMENTE una materia (materia_id obligatorio)."""
    with pytest.raises(ComisionInvalidaError):
        Comision(codigo="C1", nombre="Comisión 1", materia_id=None)


def test_comision_con_materia_vacia_es_rechazada():
    with pytest.raises(ComisionInvalidaError):
        Comision(codigo="C1", nombre="Comisión 1", materia_id="")


def test_comision_sin_codigo_es_rechazada():
    with pytest.raises(ComisionInvalidaError):
        Comision(codigo="", nombre="Comisión 1", materia_id="m-1")


def test_comision_sin_nombre_es_rechazada():
    with pytest.raises(ComisionInvalidaError):
        Comision(codigo="C1", nombre="", materia_id="m-1")


def test_comision_inmutable():
    c = Comision(codigo="C1", nombre="Comisión 1", materia_id="m-1")
    with pytest.raises((AttributeError, TypeError)):
        c.codigo = "OTRO"  # type: ignore[misc]
