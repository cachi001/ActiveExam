"""Tests de la cadena de custodia de 4 etapas (C-12, dominio PURO).

Cubre: las 4 firmas acumulativas coexisten; hash divergente en etapa 2 (backend) y
etapa 3 (worker) levanta ManipulacionDetectada (no descarte silencioso); el output
de re-inferencia se firma. La firma maestra asimetrica y la re-inferencia se
ejercen con DOBLES de los puertos (sin cryptography ni motor de vision reales).
"""

from __future__ import annotations

import hashlib

import pytest

from app.domain.entities.evidence import Evidencia
from app.domain.evidence import custody_chain as cc


class FakeSigner(cc.MasterSignerPort):
    """Firma asimetrica simulada (determinista) para los tests. NO es la real."""

    def firmar(self, mensaje: bytes) -> str:
        return "sig-" + hashlib.sha256(b"priv|" + mensaje).hexdigest()

    def verificar(self, mensaje: bytes, firma: str) -> bool:
        return firma == self.firmar(mensaje)


class FakeInference(cc.ServerInferencePort):
    def inferir(self, clip_bytes: bytes) -> dict[str, str]:
        return {"veredicto": "sin_anomalia", "frames": str(len(clip_bytes))}


CLIP = b"clip-binario-de-evidencia-5s"


def _evidencia_etapa1() -> Evidencia:
    h = cc.hash_clip(CLIP)
    return Evidencia(
        session_id="sess-1",
        uri_bucket="s3://evidence/clip-1",
        hash_cliente=h,
        firma_cliente="hmac-cliente-xyz",
    )


def test_cadena_de_4_firmas_coexisten_acumulativas() -> None:
    signer = FakeInference and FakeSigner()
    ev = _evidencia_etapa1()
    ev = cc.aplicar_etapa2(ev, clip_bytes=CLIP)
    ev = cc.aplicar_firma_maestra(ev, clip_bytes=CLIP, signer=signer)
    ev = cc.aplicar_reinferencia(
        ev, clip_bytes=CLIP, inferencia=FakeInference(), signer=signer
    )
    # Las 4 etapas coexisten: ninguna sobrescribe a la previa (RN-CC-02).
    assert ev.hash_cliente and ev.firma_cliente
    assert ev.hash_backend == ev.hash_cliente
    assert ev.firma_maestra and ev.firma_maestra.startswith("sig-")
    assert ev.output_reinferencia.get("firma_output")
    assert cc.cadena_completa(ev) is True


def test_output_reinferencia_firmado_verificable_con_clave_publica() -> None:
    signer = FakeSigner()
    ev = cc.aplicar_etapa2(_evidencia_etapa1(), clip_bytes=CLIP)
    ev = cc.aplicar_reinferencia(
        ev, clip_bytes=CLIP, inferencia=FakeInference(), signer=signer
    )
    salida = dict(ev.output_reinferencia)
    firma = salida.pop("firma_output")
    payload = cc._canonico_output(salida)
    assert signer.verificar(payload.encode("utf-8"), firma) is True


def test_hash_divergente_en_backend_es_manipulacion() -> None:
    ev = _evidencia_etapa1()
    # El clip almacenado fue alterado respecto al hash que firmo el cliente.
    with pytest.raises(cc.ManipulacionDetectada) as exc:
        cc.aplicar_etapa2(ev, clip_bytes=b"clip-ALTERADO")
    assert exc.value.etapa == "backend"


def test_hash_divergente_en_worker_es_manipulacion() -> None:
    ev = cc.aplicar_etapa2(_evidencia_etapa1(), clip_bytes=CLIP)
    # En el worker, el clip re-descargado no coincide con hash_backend.
    with pytest.raises(cc.ManipulacionDetectada) as exc:
        cc.aplicar_firma_maestra(ev, clip_bytes=b"otro-clip", signer=FakeSigner())
    assert exc.value.etapa == "worker"


def test_manipulacion_no_se_descarta_en_silencio() -> None:
    # La deteccion levanta excepcion con datos forenses (etapa + hashes), nunca None.
    ev = _evidencia_etapa1()
    try:
        cc.aplicar_etapa2(ev, clip_bytes=b"tamper")
        raise AssertionError("debio levantar ManipulacionDetectada")
    except cc.ManipulacionDetectada as e:
        assert e.esperado and e.calculado and e.esperado != e.calculado
