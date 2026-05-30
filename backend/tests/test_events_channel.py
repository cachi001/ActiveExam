"""Tests del canal WS del estudiante (C-10, logica sin red, DD-16).

Cubre el routing del ``StudentChannelSession``: evento -> ingesta+ack, heartbeat ->
prueba de vida, comando backend->cliente, y que el session_id se ata al handshake
(no se confia en el del mensaje). El handshake/JWT se prueba via authenticate.
"""

from __future__ import annotations

import asyncio

from app.application.events.ingestion import EventIngestionService
from app.domain.biometrics import custody
from app.domain.entities.session import Sesion
from app.domain.events.schema import construir_entrante
from app.domain.events.signature import firmar_evento
from app.infrastructure.messaging.backplane import build_backplane
from app.presentation.api.v1.events.channel import Handshake, StudentChannelSession

from tests.test_biometrics_service import InMemoryEventRepo, InMemorySessionRepo

_CLAVE = custody.derivar_clave_sesion(secreto_maestro=b"secreto", session_id="sess-1")


def _firma(**campos) -> str:
    ev = construir_entrante({**campos, "firma": "x"})
    return firmar_evento(ev, clave_sesion=_CLAVE)


def _build_channel():
    sesion = Sesion(id="sess-1", user_id="u1", exam_id="e1", clave_sesion=_CLAVE)
    eventos = InMemoryEventRepo()
    publicados: list = []

    async def pub(canal, evento):
        publicados.append((canal, evento))

    backplane = build_backplane("postgres", pub)
    ingestion = EventIngestionService(
        eventos=eventos, sesiones=InMemorySessionRepo(sesion), backplane=backplane
    )
    enviados: list = []

    async def send_command(cmd):
        enviados.append(cmd)

    canal = StudentChannelSession(
        handshake=Handshake(session_id="sess-1", jwt="jwt"),
        ingestion=ingestion,
        send_command=send_command,
    )
    return canal, eventos, publicados, enviados


def _evento_msg(**over) -> dict:
    base = {
        "id": "evt-1", "session_id": "sess-1", "exam_id": "e1",
        "tipo": "multiples_rostros", "severidad": "alta",
        "ts_client": "2026-05-30T10:00:00Z", "payload": {},
        "schema_version": 1,
    }
    base.update(over)
    base["firma"] = _firma(**{k: base[k] for k in (
        "id", "session_id", "exam_id", "tipo", "severidad", "ts_client", "schema_version",
    )})
    return base


def test_evento_por_canal_se_ingesta_y_ackea() -> None:
    async def run() -> None:
        canal, eventos, publicados, _ = _build_channel()
        ack = await canal.on_message(_evento_msg())
        assert ack["ack"] == "evento"
        assert ack["persistido"] is True
        assert len(eventos.items) == 1
        assert len(publicados) == 1  # fan-out

    asyncio.run(run())


def test_heartbeat_por_canal_es_prueba_de_vida() -> None:
    async def run() -> None:
        canal, _, _, _ = _build_channel()
        ack = await canal.on_message(
            _evento_msg(id="hb-1", tipo="heartbeat", severidad="baseline")
        )
        assert ack["ack"] == "heartbeat"
        assert ack["prueba_de_vida"] is True

    asyncio.run(run())


def test_comando_backend_a_cliente_se_emite_por_el_canal() -> None:
    async def run() -> None:
        canal, _, _, enviados = _build_channel()
        await canal.emitir_comando({"cmd": "recapturar_referencia"})
        assert enviados == [{"cmd": "recapturar_referencia"}]
        assert canal.comandos_enviados == [{"cmd": "recapturar_referencia"}]

    asyncio.run(run())


def test_session_id_se_ata_al_handshake_no_al_mensaje() -> None:
    async def run() -> None:
        canal, eventos, _, _ = _build_channel()
        # El mensaje trae otro session_id; el canal lo sobreescribe con el del
        # handshake (no se confia en el cliente).
        msg = _evento_msg()
        msg["session_id"] = "sesion-ajena"
        ack = await canal.on_message(msg)
        assert ack["persistido"] is True
        assert eventos.items[0].session_id == "sess-1"  # el del handshake

    asyncio.run(run())
