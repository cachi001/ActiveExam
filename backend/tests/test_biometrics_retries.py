"""Tests de la maquina de reintentos (C-09, logica pura, RN-BIO-04, L2.5)."""

from __future__ import annotations

import pytest

from app.domain.biometrics.retries import (
    MAX_REINTENTOS,
    EstadoVerificacion,
    ReintentosAgotadosError,
    VeredictoIntento,
)


def test_exito_al_primer_intento_verifica_y_cierra() -> None:
    estado = EstadoVerificacion.inicial()
    nuevo, veredicto = estado.registrar_intento(exito=True)
    assert veredicto == VeredictoIntento.VERIFICADO
    assert nuevo.cerrado is True


def test_dos_reintentos_disponibles_antes_de_escalar() -> None:
    estado = EstadoVerificacion.inicial()
    # Intento 1 falla -> queda reintento.
    estado, v1 = estado.registrar_intento(exito=False)
    assert v1 == VeredictoIntento.REINTENTO_DISPONIBLE
    assert estado.reintentos_restantes == MAX_REINTENTOS - 1
    # Intento 2 falla -> aun queda 1 reintento.
    estado, v2 = estado.registrar_intento(exito=False)
    assert v2 == VeredictoIntento.REINTENTO_DISPONIBLE
    assert estado.reintentos_restantes == 0
    assert estado.cerrado is False


def test_tercer_fallo_escala_a_proctor_sin_abortar() -> None:
    estado = EstadoVerificacion.inicial()
    estado, _ = estado.registrar_intento(exito=False)  # 1
    estado, _ = estado.registrar_intento(exito=False)  # 2
    estado, veredicto = estado.registrar_intento(exito=False)  # 3 -> escala
    assert veredicto == VeredictoIntento.ESCALAR_A_PROCTOR
    assert estado.cerrado is True
    assert estado.intentos_fallidos == 3
    # Sin abort ni sancion: la maquina NO tiene un estado "abortado"/"sancionado".
    assert not hasattr(estado, "abortado")
    assert not hasattr(estado, "sancionado")


def test_reintento_disponible_permite_recuperarse_con_exito() -> None:
    estado = EstadoVerificacion.inicial()
    estado, _ = estado.registrar_intento(exito=False)  # falla 1
    estado, veredicto = estado.registrar_intento(exito=True)  # se recupera
    assert veredicto == VeredictoIntento.VERIFICADO
    assert estado.cerrado is True


def test_no_se_puede_procesar_sobre_estado_cerrado() -> None:
    estado = EstadoVerificacion.inicial()
    estado, _ = estado.registrar_intento(exito=True)
    with pytest.raises(ReintentosAgotadosError):
        estado.registrar_intento(exito=False)
