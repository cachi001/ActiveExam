"""Firma HMAC del evento/heartbeat (PURO, RN-GLB-01, RN-HB-01, C-10 D2).

El backend valida la firma HMAC-SHA256 de CADA evento contra la CLAVE DE SESION
ROTATIVA (emitida por C-09) ANTES de persistir (zero trust del cliente). Un evento
sin firma o con firma invalida se RECHAZA (no se persiste ni propaga).

El MENSAJE CANONICO firmado debe ser identico en cliente y backend: se construye de
forma determinista a partir de los campos del contrato (mismo orden, mismo
separador). Reusa la primitiva HMAC de ``app.domain.biometrics.custody``
(``firmar``/``verificar_firma``), que es stdlib pura.

PUREZA (D1): sin framework; ``hmac`` via custody (stdlib).
"""

from __future__ import annotations

from app.domain.biometrics import custody
from app.domain.events.schema import EventoEntrante

# Separador del mensaje canonico (mismo que usa el cliente al firmar).
_SEP = "|"


class FirmaInvalidaError(ValueError):
    """La firma HMAC del evento no valida contra la clave de sesion (rechazo)."""


class EventoSinFirmaError(ValueError):
    """El evento llego sin firma: se rechaza (no se persiste ni propaga)."""


def mensaje_canonico(evento: EventoEntrante) -> bytes:
    """Construye el mensaje canonico a firmar/verificar (determinista).

    Orden fijo de los campos del contrato (sin ``ts_backend``, que lo completa el
    backend, ni la propia ``firma``). Cliente y backend DEBEN construirlo igual."""
    partes = [
        evento.id,
        evento.session_id,
        evento.exam_id,
        evento.tipo.value,
        evento.severidad.value,
        evento.ts_client,
        str(evento.schema_version),
    ]
    return _SEP.join(partes).encode("utf-8")


def firmar_evento(evento: EventoEntrante, *, clave_sesion: str) -> str:
    """Firma el mensaje canonico del evento con la clave de sesion (HMAC-SHA256).

    Util para producir la VERSION CONFIABLE server-side (re-firma, RN-GLB-01) y para
    que el cliente firme con la misma derivacion."""
    return custody.firmar(clave_sesion=clave_sesion, mensaje=mensaje_canonico(evento))


def validar_firma(evento: EventoEntrante, *, clave_sesion: str) -> None:
    """Valida la firma del evento ANTES de persistir (zero trust, C-10 D2).

    Levanta ``EventoSinFirmaError`` si no hay firma, ``FirmaInvalidaError`` si no
    valida. No devuelve nada: el caso de uso solo persiste si esto no lanza."""
    if not evento.firma:
        raise EventoSinFirmaError("evento sin firma: rechazado (zero trust)")
    ok = custody.verificar_firma(
        clave_sesion=clave_sesion,
        mensaje=mensaje_canonico(evento),
        firma=evento.firma,
    )
    if not ok:
        raise FirmaInvalidaError("firma HMAC invalida: evento rechazado")
