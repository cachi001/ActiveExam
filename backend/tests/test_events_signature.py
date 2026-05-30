"""Tests de la firma HMAC del evento (C-10, logica pura, RN-GLB-01, RN-HB-01)."""

from __future__ import annotations

import pytest

from app.domain.biometrics import custody
from app.domain.events.schema import Severidad, TipoEvento, construir_entrante
from app.domain.events.signature import (
    EventoSinFirmaError,
    FirmaInvalidaError,
    firmar_evento,
    mensaje_canonico,
    validar_firma,
)

_CLAVE = custody.derivar_clave_sesion(
    secreto_maestro=b"secreto-maestro", session_id="s1"
)


def _evento(firma: str | None):
    return construir_entrante(
        {
            "id": "evt-1",
            "session_id": "s1",
            "exam_id": "e1",
            "tipo": "multiples_rostros",
            "severidad": "alta",
            "ts_client": "2026-05-30T10:00:00Z",
            "payload": {},
            "firma": firma if firma is not None else "x",
            "schema_version": 1,
        }
    )


def test_firma_valida_se_acepta() -> None:
    ev = _evento("x")
    firma = firmar_evento(ev, clave_sesion=_CLAVE)
    ev_firmado = _evento(firma)
    validar_firma(ev_firmado, clave_sesion=_CLAVE)  # no lanza


def test_firma_invalida_se_rechaza() -> None:
    ev = _evento("00" * 32)
    with pytest.raises(FirmaInvalidaError):
        validar_firma(ev, clave_sesion=_CLAVE)


def test_evento_sin_firma_se_rechaza() -> None:
    # firma vacia -> tratado como sin firma.
    ev = _evento("x")
    object.__setattr__(ev, "firma", "")
    with pytest.raises(EventoSinFirmaError):
        validar_firma(ev, clave_sesion=_CLAVE)


def test_firma_con_otra_clave_no_valida() -> None:
    ev = _evento("x")
    firma = firmar_evento(ev, clave_sesion=_CLAVE)
    otra = custody.derivar_clave_sesion(secreto_maestro=b"otro", session_id="s1")
    ev_firmado = _evento(firma)
    with pytest.raises(FirmaInvalidaError):
        validar_firma(ev_firmado, clave_sesion=otra)


def test_mensaje_canonico_no_incluye_ts_backend_ni_firma() -> None:
    ev = _evento("x")
    msg = mensaje_canonico(ev).decode("utf-8")
    assert "evt-1" in msg and "s1" in msg
    # ts_backend no participa (lo completa el backend); la firma no se firma a si misma.
    assert msg.count("|") == 6  # 7 campos -> 6 separadores


def test_tamper_en_un_campo_invalida_la_firma() -> None:
    ev = _evento("x")
    firma = firmar_evento(ev, clave_sesion=_CLAVE)
    # Cambia la severidad: la firma ya no debe validar (integridad).
    ev_tamper = construir_entrante(
        {
            "id": "evt-1", "session_id": "s1", "exam_id": "e1",
            "tipo": "multiples_rostros", "severidad": "media",  # cambiado
            "ts_client": "2026-05-30T10:00:00Z", "payload": {},
            "firma": firma, "schema_version": 1,
        }
    )
    with pytest.raises(FirmaInvalidaError):
        validar_firma(ev_tamper, clave_sesion=_CLAVE)
