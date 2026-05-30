"""Logica del canal WebSocket del estudiante (C-10, DD-16), testeable sin red.

Separa la LOGICA del canal (handshake + routing de mensajes + comandos) del
transporte WebSocket concreto, para poder testearla sin levantar un socket:

- ``StudentChannelSession``: encapsula el handshake (session_id + JWT + last_event_id)
  y el ROUTING de mensajes entrantes (evento / heartbeat / ack de comando) hacia el
  ``EventIngestionService``, y la EMISION de comandos backend->cliente.

El WebSocket bidireccional del estudiante es FIJO (DD-16): no esta bajo la decision
de transporte de C-03 (eso es el panel/backplane). El JWT se valida en el handshake
contra el JWKS (C-06 ``authenticate_handshake``) y periodicamente
(``RealtimeRevalidator``).

L2.5: el canal solo transporta y persiste; ninguna sancion se deriva (RN-RV-07).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.application.events.ingestion import EventIngestionService

# Emisor de comandos backend->cliente (lo provee el transporte WS concreto).
CommandSender = Callable[[dict], Awaitable[None]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class Handshake:
    """Parametros del handshake del canal (DD-16, RN-AU-03)."""

    session_id: str
    jwt: str
    last_event_id: str | None = None


@dataclass
class StudentChannelSession:
    """Sesion de canal del estudiante: rutea mensajes entrantes y emite comandos.

    ``send_command`` lo inyecta el transporte (el WS real). El routing distingue
    ``tipo == 'heartbeat'`` (prueba de vida) del resto (eventos de telemetria)."""

    handshake: Handshake
    ingestion: EventIngestionService
    send_command: CommandSender
    comandos_enviados: list[dict] = field(default_factory=list)

    async def on_message(self, mensaje: dict) -> dict:
        """Procesa un mensaje entrante (evento o heartbeat) y devuelve un ack.

        El ``ts_backend`` se completa aqui (no el cliente). Devuelve un ack con el
        resultado (persistido / prueba_de_vida / rechazo)."""
        # Asocia el evento a la sesion del handshake (no se confia en otro session_id).
        mensaje = {**mensaje, "session_id": self.handshake.session_id}
        ts_backend = _now_iso()

        if mensaje.get("tipo") == "heartbeat":
            vivo = await self.ingestion.ingest_heartbeat(mensaje, ts_backend=ts_backend)
            return {"ack": "heartbeat", "prueba_de_vida": vivo}

        resultado = await self.ingestion.ingest(mensaje, ts_backend=ts_backend)
        return {
            "ack": "evento",
            "persistido": resultado.persistido,
            "evento_id": resultado.evento_id,
        }

    async def emitir_comando(self, comando: dict) -> None:
        """Emite un comando backend->cliente por el canal bidireccional (DD-16)."""
        await self.send_command(comando)
        self.comandos_enviados.append(comando)
