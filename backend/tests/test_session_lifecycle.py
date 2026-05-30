"""Tests de logica PURA del ciclo de vida de la Sesion (sin DB).

Verifica la capability ``session-lifecycle-enum`` a nivel de dominio: el enum de
estados y las transiciones validas/invalidas. La invariante en el MOTOR (la base
rechaza un estado fuera del enum aun por fuera de la aplicacion) se prueba en
``test_db_invariants.py`` con ``@pytest.mark.requires_stack``.

Estos tests no tocan la base: ejercitan la maquina de estados del dominio puro.
"""

from __future__ import annotations

import pytest

from app.domain.entities.session import EstadoSesion, Sesion


def test_estado_sesion_enum_values() -> None:
    """El enum expone exactamente los cinco estados del dominio (`04` Sesion)."""
    assert {e.value for e in EstadoSesion} == {
        "iniciada",
        "activa",
        "finalizada",
        "flaggeada",
        "cerrada",
    }


def test_transicion_valida_iniciada_a_activa() -> None:
    sesion = Sesion.crear(user_id="u1", exam_id="e1", clave_sesion="k1")
    assert sesion.estado is EstadoSesion.INICIADA

    activa = sesion.transicionar(EstadoSesion.ACTIVA)
    assert activa.estado is EstadoSesion.ACTIVA
    # Inmutabilidad: la transicion devuelve una nueva instancia.
    assert sesion.estado is EstadoSesion.INICIADA


def test_flujo_completo_valido() -> None:
    sesion = Sesion.crear(user_id="u1", exam_id="e1", clave_sesion="k1")
    sesion = sesion.transicionar(EstadoSesion.ACTIVA)
    sesion = sesion.transicionar(EstadoSesion.FLAGGEADA)
    sesion = sesion.transicionar(EstadoSesion.FINALIZADA)
    sesion = sesion.transicionar(EstadoSesion.CERRADA)
    assert sesion.estado is EstadoSesion.CERRADA


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (EstadoSesion.INICIADA, EstadoSesion.FINALIZADA),  # salta activa
        (EstadoSesion.CERRADA, EstadoSesion.ACTIVA),  # estado terminal
        (EstadoSesion.FINALIZADA, EstadoSesion.INICIADA),  # retroceso
        (EstadoSesion.ACTIVA, EstadoSesion.INICIADA),  # retroceso
    ],
)
def test_transicion_invalida_rechazada(
    origen: EstadoSesion, destino: EstadoSesion
) -> None:
    sesion = Sesion.crear(user_id="u1", exam_id="e1", clave_sesion="k1")
    sesion = sesion._con_estado(origen)  # posiciona el estado de partida
    with pytest.raises(ValueError, match="transicion invalida"):
        sesion.transicionar(destino)


def test_estado_cerrada_es_terminal() -> None:
    sesion = Sesion.crear(user_id="u1", exam_id="e1", clave_sesion="k1")
    cerrada = sesion._con_estado(EstadoSesion.CERRADA)
    for destino in EstadoSesion:
        with pytest.raises(ValueError):
            cerrada.transicionar(destino)
