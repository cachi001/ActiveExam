"""Tests del gate de liveness hibrido (C-09, logica pura, RN-BIO-05, DD-18)."""

from __future__ import annotations

import pytest

from app.domain.biometrics.liveness import (
    EvidenciaLiveness,
    LivenessInvalidoError,
    RetoActivo,
    SenalesPasivas,
    liveness_exitoso,
    validar_retos_solicitados,
)


def _pasivo_ok() -> SenalesPasivas:
    return SenalesPasivas(
        parpadeo_detectado=True, micro_movimientos=True, profundidad_3d_coherente=True
    )


def test_liveness_exitoso_con_pasivo_y_reto_resuelto() -> None:
    ev = EvidenciaLiveness(
        pasivas=_pasivo_ok(),
        retos_solicitados=(RetoActivo.PARPADEAR,),
        retos_resueltos=(RetoActivo.PARPADEAR,),
    )
    assert liveness_exitoso(ev) is True


def test_foto_plana_sin_profundidad_no_pasa_liveness() -> None:
    # Una foto/video pregrabado no tiene profundidad 3D coherente ni parpadeo vivo.
    ev = EvidenciaLiveness(
        pasivas=SenalesPasivas(
            parpadeo_detectado=False, micro_movimientos=False, profundidad_3d_coherente=False
        ),
        retos_solicitados=(RetoActivo.PARPADEAR,),
        retos_resueltos=(RetoActivo.PARPADEAR,),
    )
    assert liveness_exitoso(ev) is False


def test_reto_no_resuelto_invalida_liveness() -> None:
    ev = EvidenciaLiveness(
        pasivas=_pasivo_ok(),
        retos_solicitados=(RetoActivo.GIRAR_IZQUIERDA,),
        retos_resueltos=(),  # no resolvio el reto
    )
    assert liveness_exitoso(ev) is False


def test_camara_virtual_detectada_invalida_liveness() -> None:
    # La heuristica de integridad reporta camara virtual -> capa de defensa (DD-18).
    ev = EvidenciaLiveness(
        pasivas=_pasivo_ok(),
        retos_solicitados=(RetoActivo.PARPADEAR,),
        retos_resueltos=(RetoActivo.PARPADEAR,),
        camara_virtual_detectada=True,
    )
    assert liveness_exitoso(ev) is False


def test_dos_retos_ambos_resueltos_pasan() -> None:
    ev = EvidenciaLiveness(
        pasivas=_pasivo_ok(),
        retos_solicitados=(RetoActivo.GIRAR_DERECHA, RetoActivo.SONREIR),
        retos_resueltos=(RetoActivo.SONREIR, RetoActivo.GIRAR_DERECHA),
    )
    assert liveness_exitoso(ev) is True


def test_dos_retos_uno_no_resuelto_falla() -> None:
    ev = EvidenciaLiveness(
        pasivas=_pasivo_ok(),
        retos_solicitados=(RetoActivo.GIRAR_DERECHA, RetoActivo.SONREIR),
        retos_resueltos=(RetoActivo.SONREIR,),
    )
    assert liveness_exitoso(ev) is False


def test_cantidad_de_retos_fuera_de_rango_es_invalida() -> None:
    with pytest.raises(LivenessInvalidoError):
        validar_retos_solicitados(())  # 0 retos
    with pytest.raises(LivenessInvalidoError):
        validar_retos_solicitados(
            (RetoActivo.PARPADEAR, RetoActivo.SONREIR, RetoActivo.ACERCARSE)
        )  # 3 retos
