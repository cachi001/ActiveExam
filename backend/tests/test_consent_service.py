"""Tests del ConsentService con puertos EN MEMORIA (C-08).

Cubre el flujo completo sin DB:
- record_consent: acuse con timestamp+hash; sin accion afirmativa -> 422; el repo
  inmutable no expone update/delete (la inmutabilidad de motor la prueba
  test_db_invariants con stack).
- choose_alternative: deja traza inmutable en el audit log y escala por la cola;
  no aborta.
- gate (D4): consentido -> avanza+biometria; alternativa -> avanza sin biometria;
  no resuelto -> 403.

Los puertos en memoria implementan el contrato real de C-05 (sin mock de DB).
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.consent.service import (
    ACCION_VIA_ALTERNATIVA,
    TOPIC_ESCALACION_PROCTOR,
    ConsentService,
)
from app.domain.audit_chain import AuditEntry, construir_cadena, verificar_cadena
from app.domain.consent_flow.errors import (
    ConsentNotResolvedError,
    MissingAffirmativeActionError,
)
from app.domain.consent_flow.rules import ResolucionConsentimiento
from app.domain.entities.consent import Consentimiento
from app.domain.repositories.ports import AuditLogRepository, ConsentRepository
from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage


class InMemoryConsentRepo(ConsentRepository):
    """Repo inmutable: solo add/get/list (sin update/delete), como el puerto C-05."""

    def __init__(self) -> None:
        self._items: list[Consentimiento] = []
        self._seq = 0

    async def add(self, entity: Consentimiento) -> Consentimiento:
        self._seq += 1
        c = Consentimiento(
            id=str(self._seq),
            user_id=entity.user_id,
            exam_id=entity.exam_id,
            version_texto=entity.version_texto,
            timestamp=entity.timestamp,
            hash=entity.hash,
        )
        self._items.append(c)
        return c

    async def get(self, entity_id: str) -> Consentimiento | None:
        return next((c for c in self._items if c.id == entity_id), None)

    async def list(self) -> list[Consentimiento]:
        return list(self._items)


class InMemoryAuditRepo(AuditLogRepository):
    def __init__(self) -> None:
        self._items: list[AuditEntry] = []

    async def append(self, entity: AuditEntry) -> AuditEntry:
        encadenada = construir_cadena(self._items + [entity])[-1]
        self._items.append(encadenada)
        return encadenada

    async def get(self, entity_id: str) -> AuditEntry | None:
        return None

    async def list(self) -> list[AuditEntry]:
        return list(self._items)

    async def verificar_cadena(self) -> bool:
        return verificar_cadena(self._items)


class FakeQueue(MessageQueuePort):
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue(self, topic: str, payload: dict) -> str:
        self.enqueued.append((topic, payload))
        return f"msg-{len(self.enqueued)}"

    async def dequeue(self, topic: str) -> QueuedMessage | None:
        return None

    async def ack(self, message_id: str) -> None:
        return None

    async def health_check(self) -> bool:
        return True


def _service():
    consents, audit, queue = InMemoryConsentRepo(), InMemoryAuditRepo(), FakeQueue()
    return ConsentService(consents, audit, queue), consents, audit, queue


def test_record_consent_persiste_con_hash() -> None:
    async def run() -> None:
        svc, consents, _, _ = _service()
        acuse = await svc.record_consent(
            user_id="u1",
            exam_id="e1",
            version_texto=None,
            affirmative_action=True,
            timestamp="2026-05-30T10:00:00Z",
        )
        assert acuse.id is not None
        assert len(acuse.hash) == 64
        assert acuse.timestamp == "2026-05-30T10:00:00Z"
        assert len(await consents.list()) == 1

    asyncio.run(run())


def test_record_consent_sin_accion_afirmativa_no_persiste() -> None:
    async def run() -> None:
        svc, consents, _, _ = _service()
        with pytest.raises(MissingAffirmativeActionError):
            await svc.record_consent(
                user_id="u1",
                exam_id="e1",
                version_texto=None,
                affirmative_action=False,
                timestamp="t",
            )
        assert await consents.list() == []

    asyncio.run(run())


def test_consent_repo_no_expone_update_ni_delete() -> None:
    # Garantia de inmutabilidad en el CONTRATO (puerto): sin metodos de mutacion.
    repo = InMemoryConsentRepo()
    assert not hasattr(repo, "update")
    assert not hasattr(repo, "delete")


def test_choose_alternative_audita_y_escala_sin_abortar() -> None:
    async def run() -> None:
        svc, _, audit, queue = _service()
        msg_id = await svc.choose_alternative(
            user_id="u1", exam_id="e1", timestamp="2026-05-30T10:00:00Z"
        )
        assert msg_id == "msg-1"
        # Escalo a proctor por la cola.
        assert queue.enqueued[0][0] == TOPIC_ESCALACION_PROCTOR
        # Dejo traza inmutable y encadenada en el audit log.
        entradas = await audit.list()
        assert entradas[0].accion == ACCION_VIA_ALTERNATIVA
        assert await audit.verificar_cadena() is True

    asyncio.run(run())


def test_gate_con_consentimiento_habilita_biometria() -> None:
    async def run() -> None:
        svc, _, _, _ = _service()
        await svc.record_consent(
            user_id="u1", exam_id="e1", version_texto=None,
            affirmative_action=True, timestamp="t",
        )
        assert await svc.resolve(user_id="u1", exam_id="e1") == ResolucionConsentimiento.CONSENTIDO
        assert await svc.evaluate_gate(user_id="u1", exam_id="e1") is True
        assert await svc.biometria_habilitada(user_id="u1", exam_id="e1") is True

    asyncio.run(run())


def test_gate_con_alternativa_avanza_sin_biometria() -> None:
    async def run() -> None:
        svc, _, _, _ = _service()
        await svc.choose_alternative(user_id="u1", exam_id="e1", timestamp="t")
        assert await svc.resolve(user_id="u1", exam_id="e1") == ResolucionConsentimiento.VIA_ALTERNATIVA
        assert await svc.evaluate_gate(user_id="u1", exam_id="e1") is True
        assert await svc.biometria_habilitada(user_id="u1", exam_id="e1") is False

    asyncio.run(run())


def test_gate_sin_resolucion_bloquea_biometria() -> None:
    async def run() -> None:
        svc, _, _, _ = _service()
        assert await svc.resolve(user_id="u1", exam_id="e1") == ResolucionConsentimiento.NO_RESUELTO
        with pytest.raises(ConsentNotResolvedError):
            await svc.evaluate_gate(user_id="u1", exam_id="e1")

    asyncio.run(run())


def test_gate_es_por_examen() -> None:
    async def run() -> None:
        svc, _, _, _ = _service()
        await svc.record_consent(
            user_id="u1", exam_id="e1", version_texto=None,
            affirmative_action=True, timestamp="t",
        )
        # Consentimiento de e1 no resuelve e2.
        assert await svc.resolve(user_id="u1", exam_id="e2") == ResolucionConsentimiento.NO_RESUELTO

    asyncio.run(run())
