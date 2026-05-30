"""Puerto de backplane de fan-out + adaptadores swappables (C-10 D3).

El fan-out del evento persistido a los paneles va DETRAS DE PUERTO: ``EventBackplane``.
El adaptador concreto lo decide C-03 (ganador medido por metrica), sin reescribir
la logica de ingesta:
- ``PostgresListenNotifyBackplane``: ``LISTEN/NOTIFY`` de Postgres (hipotesis A4 por
  defecto, DD-16/DD-19).
- ``RedisPubSubBackplane``: Redis Pub/Sub (si C-03 lo promueve por metrica).

La seleccion la hace ``build_backplane`` por configuracion (``messaging_backend``).
La logica de ingesta (C-10) depende SOLO de este puerto, nunca del adaptador.

El cliente concreto (asyncpg LISTEN / redis.asyncio) se inyecta en produccion; aqui
se deja el contrato + adaptadores que delegan en un publisher inyectable para tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

# Publisher inyectable: (canal, payload) -> coroutine. En produccion envuelve el
# NOTIFY de asyncpg o el PUBLISH de redis; en tests, un doble en memoria.
Publisher = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventBackplane(ABC):
    """Puerto de fan-out de eventos a paneles (swappable, ganador de C-03)."""

    @abstractmethod
    async def publish(self, *, canal: str, evento: dict[str, Any]) -> None:
        """Publica el evento validado en el ``canal`` (sesion/examen) del backplane."""

    @abstractmethod
    def canal_de(self, *, exam_id: str) -> str:
        """Canal del backplane por examen al que se suscriben los paneles."""


class _BasePublisherBackplane(EventBackplane):
    """Base que delega en un publisher inyectable y deriva el canal por examen."""

    _PREFIJO = "panel"

    def __init__(self, publisher: Publisher) -> None:
        self._publish = publisher

    async def publish(self, *, canal: str, evento: dict[str, Any]) -> None:
        await self._publish(canal, evento)

    def canal_de(self, *, exam_id: str) -> str:
        return f"{self._PREFIJO}:{exam_id}"


class PostgresListenNotifyBackplane(_BasePublisherBackplane):
    """Backplane sobre Postgres LISTEN/NOTIFY (default A4, DD-16)."""


class RedisPubSubBackplane(_BasePublisherBackplane):
    """Backplane sobre Redis Pub/Sub (si C-03 lo promueve por metrica)."""


def build_backplane(backend: str, publisher: Publisher) -> EventBackplane:
    """Selecciona el adaptador por configuracion (``messaging_backend``, C-03).

    ``postgres`` (default A4) -> LISTEN/NOTIFY; ``redis`` -> Pub/Sub. La logica de
    ingesta no cambia: solo el adaptador inyectado."""
    if backend == "redis":
        return RedisPubSubBackplane(publisher)
    # Default A4 (postgres) y cualquier otro valor caen a LISTEN/NOTIFY.
    return PostgresListenNotifyBackplane(publisher)
