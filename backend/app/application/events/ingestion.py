"""Caso de uso de ingesta de eventos (aplicacion, C-10).

Implementa la mecanica del Flujo 3 con zero trust del cliente (RN-GLB-01):

1. Construye el ``EventoEntrante`` validando campos + version (RN-EV-05); evento
   mal formado o version no soportada -> RECHAZO (no persiste).
2. Recupera la clave de sesion rotativa (emitida por C-09) de la ``Sesion``.
3. VALIDA la firma HMAC ANTES de persistir (C-10 D2); sin firma / invalida ->
   RECHAZO (no persiste, no fan-out), registrando el rechazo.
4. Completa ``ts_backend`` (no lo pone el cliente) y produce la VERSION CONFIABLE
   server-side: re-firma con la clave de sesion (RN-GLB-01).
5. PERSISTE en la hypertable (append-only) y hace FAN-OUT por el backplane.

El sistema NUNCA sanciona automaticamente (L2.5): la ingesta termina en
persistir + fan-out; ninguna severidad dispara accion punitiva.

Depende de PUERTOS: repo de Sesion (clave), repo de Evento (append-only,
hypertable), backplane (fan-out, swappable). NUNCA de adaptadores.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.event import Evento
from app.domain.events import signature
from app.domain.events.schema import (
    EventoEntrante,
    construir_entrante,
)
from app.domain.events.signature import (
    EventoSinFirmaError,
    FirmaInvalidaError,
)
from app.domain.repositories.ports import EventRepository, SessionRepository
from app.infrastructure.messaging.backplane import EventBackplane


class SesionInexistenteError(ValueError):
    """No existe la sesion referida por el evento: rechazo (sin clave que validar)."""


class SesionSinClaveError(ValueError):
    """La sesion no tiene clave de sesion emitida (C-09 no verifico aun)."""


@dataclass(frozen=True, slots=True)
class IngestaResultado:
    """Resultado de ingestar un evento (para metricas/telemetria)."""

    persistido: bool
    evento_id: str | None
    es_anomalia: bool


class EventIngestionService:
    """Ingesta validada + persistencia + fan-out de eventos (C-10)."""

    def __init__(
        self,
        *,
        eventos: EventRepository,
        sesiones: SessionRepository,
        backplane: EventBackplane,
    ) -> None:
        self._eventos = eventos
        self._sesiones = sesiones
        self._backplane = backplane

    async def ingest(self, datos: dict[str, object], *, ts_backend: str) -> IngestaResultado:
        """Ingesta un evento crudo del cliente. Valida -> persiste -> fan-out.

        Levanta ``EventoMalFormadoError`` / ``VersionNoSoportadaError`` (campos /
        version), ``EventoSinFirmaError`` / ``FirmaInvalidaError`` (firma),
        ``SesionInexistenteError`` / ``SesionSinClaveError`` (sesion). En todos los
        casos de error NO se persiste ni se hace fan-out (zero trust, C-10 D2)."""
        entrante = construir_entrante(datos)  # valida campos + version (puede lanzar)

        clave = await self._clave_de_sesion(entrante.session_id)

        # VALIDA la firma ANTES de persistir (RN-GLB-01). Lanza -> rechazo.
        signature.validar_firma(entrante, clave_sesion=clave)

        # VERSION CONFIABLE server-side: completa ts_backend + re-firma con la clave
        # de la sesion (la fuente de verdad es el servidor, RN-GLB-01).
        firma_confiable = signature.firmar_evento(entrante, clave_sesion=clave)
        evento = Evento(
            session_id=entrante.session_id,
            exam_id=entrante.exam_id,
            tipo=entrante.tipo.value,
            severidad=entrante.severidad.value,
            timestamp_cliente=entrante.ts_client,
            timestamp_backend=ts_backend,
            payload=entrante.payload,
            firma=firma_confiable,
            schema_version=entrante.schema_version,
        )

        persistido = await self._eventos.append(evento)

        # FAN-OUT a paneles tras la persistencia (D3, backplane swappable). Ninguna
        # sancion se deriva aqui (L2.5): solo se transporta y persiste la senal.
        canal = self._backplane.canal_de(exam_id=entrante.exam_id)
        await self._backplane.publish(canal=canal, evento=_serializar(persistido))

        from app.domain.events.schema import es_anomalia

        return IngestaResultado(
            persistido=True,
            evento_id=persistido.id,
            es_anomalia=es_anomalia(entrante.tipo),
        )

    async def ingest_heartbeat(
        self, datos: dict[str, object], *, ts_backend: str
    ) -> bool:
        """Ingesta un heartbeat firmado (RN-HB-01). Valida la firma como prueba de
        vida; un heartbeat con firma invalida NO cuenta (devuelve ``False``)."""
        try:
            resultado = await self.ingest(datos, ts_backend=ts_backend)
        except (EventoSinFirmaError, FirmaInvalidaError):
            return False
        return resultado.persistido

    async def _clave_de_sesion(self, session_id: str) -> str:
        sesion = await self._sesiones.get(session_id)
        if sesion is None:
            raise SesionInexistenteError(f"sesion inexistente: {session_id}")
        if not sesion.clave_sesion:
            raise SesionSinClaveError(
                "la sesion no tiene clave emitida (C-09 no verifico la identidad)"
            )
        return sesion.clave_sesion


def _serializar(evento: Evento) -> dict[str, object]:
    """Serializa el evento persistido para el fan-out (contrato del panel)."""
    return {
        "id": evento.id,
        "session_id": evento.session_id,
        "exam_id": evento.exam_id,
        "tipo": evento.tipo,
        "severidad": evento.severidad,
        "ts_client": evento.timestamp_cliente,
        "ts_backend": evento.timestamp_backend,
        "payload": evento.payload,
        "schema_version": evento.schema_version,
    }
