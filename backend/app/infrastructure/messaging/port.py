"""Puerto abstracto de mensajeria.

Contrato minimo que cualquier backend de cola/transporte/backplane debe
cumplir, sea Postgres-como-cola (A4, por omision) o el ganador que decida la
PoC C-03 (RabbitMQ+Celery, Redis, etc.). El dominio y la aplicacion dependen
de ESTE puerto, nunca de un adaptador concreto.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QueuedMessage:
    """Mensaje encolado, agnostico del backend concreto."""

    id: str
    topic: str
    payload: dict[str, Any]


class MessageQueuePort(ABC):
    """Puerto de cola/transporte. Swappable segun el veredicto de C-03."""

    @abstractmethod
    async def enqueue(self, topic: str, payload: dict[str, Any]) -> str:
        """Encola un mensaje en ``topic``. Devuelve el id del mensaje."""

    @abstractmethod
    async def dequeue(self, topic: str) -> QueuedMessage | None:
        """Reclama el siguiente mensaje pendiente de ``topic`` (o ``None``)."""

    @abstractmethod
    async def ack(self, message_id: str) -> None:
        """Confirma el procesamiento exitoso de un mensaje."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Devuelve ``True`` si el backend de mensajeria responde."""
