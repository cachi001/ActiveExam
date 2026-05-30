"""Tests de aplicacion de la cadena de custodia (C-12) con dobles en memoria.

Sin DB ni storage real (esos van en tests @requires_stack): se ejercen los casos de
uso contra dobles de los puertos. Cubre: rechazo de firma cliente invalida; etapa 2
deposita + audita + encola; hash divergente -> evento critico propagado (no silencio);
worker completa las 4 firmas; durabilidad (la firma se completa al reprocesar).
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from app.application.evidence.service import (
    EvidenceCustodyService,
    EvidenceSigningWorker,
    FirmaClienteInvalidaError,
    NotificacionEvidencia,
    TOPIC_FIRMA_EVIDENCIA,
)
from app.domain.audit_chain import AuditEntry
from app.domain.entities.evidence import Evidencia
from app.domain.entities.session import Sesion
from app.domain.evidence import custody_chain as cc
from app.domain.biometrics import custody

CLAVE = "clave-de-sesion-hex"
CLIP = b"clip-de-evidencia-binario"
HASH = cc.hash_clip(CLIP)
FIRMA_OK = custody.firmar(clave_sesion=CLAVE, mensaje=HASH.encode("utf-8"))


class FakeEvidenceRepo:
    def __init__(self) -> None:
        self.items: dict[str, Evidencia] = {}
        self._n = 0

    async def add(self, ev: Evidencia) -> Evidencia:
        from dataclasses import replace

        self._n += 1
        stored = replace(ev, id=f"ev-{self._n}")
        self.items[stored.id] = stored
        return stored

    async def update(self, ev: Evidencia) -> Evidencia:
        self.items[ev.id] = ev
        return ev

    async def get(self, eid: str) -> Evidencia | None:
        return self.items.get(eid)

    async def list(self) -> list[Evidencia]:
        return list(self.items.values())


class FakeSessionRepo:
    def __init__(self, clave: str | None = CLAVE) -> None:
        self.clave = clave

    async def get(self, sid: str):
        if self.clave is None:
            return None
        return Sesion(user_id="u", exam_id="e1", clave_sesion=self.clave, id=sid)

    async def add(self, e):  # pragma: no cover - no usado
        return e

    async def update(self, e):  # pragma: no cover
        return e

    async def list(self):  # pragma: no cover
        return []


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def append(self, e: AuditEntry) -> AuditEntry:
        self.entries.append(e)
        return e

    async def get(self, eid):  # pragma: no cover
        return None

    async def list(self):
        return list(self.entries)

    async def verificar_cadena(self) -> bool:  # pragma: no cover
        return True


class FakeWorm:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.modes: list[str] = []

    def deposit(self, *, object_key, data, retain_until):
        self.store[object_key] = data
        from app.infrastructure.storage.worm import WormObject

        self.modes.append("COMPLIANCE")
        return WormObject(object_key=object_key, uri=f"worm://{object_key}", retain_until=retain_until)

    def fetch(self, *, object_key) -> bytes:
        return self.store[object_key]


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue(self, topic, payload) -> str:
        self.enqueued.append((topic, payload))
        return f"msg-{len(self.enqueued)}"

    async def dequeue(self, topic):  # pragma: no cover
        return None

    async def ack(self, mid):  # pragma: no cover
        return None

    async def health_check(self) -> bool:  # pragma: no cover
        return True


class FakeBackplane:
    def __init__(self) -> None:
        self.publicados: list[dict] = []

    async def publish(self, *, canal, evento) -> None:
        self.publicados.append({"canal": canal, **evento})

    def canal_de(self, *, exam_id) -> str:
        return f"panel:{exam_id}"


class FakeSigner(cc.MasterSignerPort):
    def firmar(self, mensaje: bytes) -> str:
        return "sig-" + hashlib.sha256(b"priv|" + mensaje).hexdigest()

    def verificar(self, mensaje: bytes, firma: str) -> bool:
        return firma == self.firmar(mensaje)


class FakeInference(cc.ServerInferencePort):
    def inferir(self, clip_bytes: bytes) -> dict[str, str]:
        return {"veredicto": "sin_anomalia"}


def _service(evidencias=None, audit=None, worm=None, cola=None, backplane=None, sesiones=None):
    return EvidenceCustodyService(
        evidencias=evidencias or FakeEvidenceRepo(),
        sesiones=sesiones or FakeSessionRepo(),
        audit=audit or FakeAudit(),
        worm=worm or FakeWorm(),
        cola=cola or FakeQueue(),
        backplane=backplane or FakeBackplane(),
    )


def _notif(firma=FIRMA_OK, hash_cli=HASH):
    return NotificacionEvidencia(
        session_id="sess-1",
        exam_id="e1",
        object_key="clip-1.bin",
        hash_cliente=hash_cli,
        firma_cliente=firma,
    )


def test_etapa2_rechaza_firma_cliente_invalida() -> None:
    svc = _service()
    with pytest.raises(FirmaClienteInvalidaError):
        asyncio.run(svc.recibir_notificacion(_notif(firma="firma-mala"), clip_bytes=CLIP, retain_until="2030-01-01"))


def test_etapa2_persiste_deposita_audita_y_encola() -> None:
    repo, audit, worm, cola = FakeEvidenceRepo(), FakeAudit(), FakeWorm(), FakeQueue()
    svc = _service(evidencias=repo, audit=audit, worm=worm, cola=cola)
    ev = asyncio.run(svc.recibir_notificacion(_notif(), clip_bytes=CLIP, retain_until="2030-01-01"))
    assert ev.hash_backend == HASH
    assert worm.store["clip-1.bin"] == CLIP
    assert worm.modes == ["COMPLIANCE"]  # Object Lock Compliance, no Governance
    assert any(e.accion == "deposito_evidencia" for e in audit.entries)
    assert cola.enqueued[0][0] == TOPIC_FIRMA_EVIDENCIA


def test_hash_divergente_en_backend_emite_evento_critico_no_silencio() -> None:
    audit, backplane = FakeAudit(), FakeBackplane()
    svc = _service(audit=audit, backplane=backplane)
    # El clip almacenado fue alterado respecto al hash firmado por el cliente.
    with pytest.raises(cc.ManipulacionDetectada):
        asyncio.run(svc.recibir_notificacion(_notif(), clip_bytes=b"ALTERADO", retain_until="2030"))
    # Traza forense + evento critico propagado (no descarte silencioso).
    assert any(e.accion == "manipulacion_detectada" for e in audit.entries)
    assert backplane.publicados
    evt = backplane.publicados[0]
    assert evt["tipo"] == cc.TIPO_EVIDENCIA_MANIPULADA
    assert evt["severidad"] == cc.SEVERIDAD_CRITICA


def test_worker_completa_las_4_firmas() -> None:
    repo, audit, worm = FakeEvidenceRepo(), FakeAudit(), FakeWorm()
    svc = _service(evidencias=repo, audit=audit, worm=worm)
    ev = asyncio.run(svc.recibir_notificacion(_notif(), clip_bytes=CLIP, retain_until="2030"))
    worker = EvidenceSigningWorker(
        evidencias=repo, audit=audit, worm=worm,
        signer=FakeSigner(), inferencia=FakeInference(), backplane=FakeBackplane(),
    )
    final = asyncio.run(worker.procesar({"evidencia_id": ev.id, "object_key": "clip-1.bin"}))
    assert cc.cadena_completa(final) is True
    assert final.firma_maestra and final.output_reinferencia.get("firma_output")


def test_worker_detecta_hash_divergente() -> None:
    repo, worm = FakeEvidenceRepo(), FakeWorm()
    svc = _service(evidencias=repo, worm=worm)
    ev = asyncio.run(svc.recibir_notificacion(_notif(), clip_bytes=CLIP, retain_until="2030"))
    # Alguien altero el binario en el storage DESPUES del deposito.
    worm.store["clip-1.bin"] = b"clip-corrupto"
    worker = EvidenceSigningWorker(
        evidencias=repo, audit=FakeAudit(), worm=worm,
        signer=FakeSigner(), inferencia=FakeInference(), backplane=FakeBackplane(),
    )
    with pytest.raises(cc.ManipulacionDetectada) as exc:
        asyncio.run(worker.procesar({"evidencia_id": ev.id, "object_key": "clip-1.bin"}))
    assert exc.value.etapa == "worker"


def test_durabilidad_la_firma_se_completa_al_reprocesar() -> None:
    # Cero perdida (RN-CC-08): si el worker cayo antes de firmar, reprocesar la misma
    # tarea completa la cadena sin perdida (la evidencia E2 ya esta en WORM).
    repo, worm = FakeEvidenceRepo(), FakeWorm()
    svc = _service(evidencias=repo, worm=worm)
    ev = asyncio.run(svc.recibir_notificacion(_notif(), clip_bytes=CLIP, retain_until="2030"))
    worker = EvidenceSigningWorker(
        evidencias=repo, audit=FakeAudit(), worm=worm,
        signer=FakeSigner(), inferencia=FakeInference(), backplane=FakeBackplane(),
    )
    final = asyncio.run(worker.procesar({"evidencia_id": ev.id, "object_key": "clip-1.bin"}))
    assert cc.cadena_completa(final)
