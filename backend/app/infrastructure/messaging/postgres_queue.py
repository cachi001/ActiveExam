"""Adaptador de mensajeria por OMISION: Postgres-como-cola (hipotesis A4).

DD-19 (empezar simple, no over-provisionar): mientras C-03 no promueva otra
pieza por metrica, la cola del MVP vive en Postgres usando
``SELECT ... FOR UPDATE SKIP LOCKED`` para reclamo concurrente y
``LISTEN/NOTIFY`` para el fan-out de baja latencia.

SWAPPABLE: este adaptador implementa ``MessageQueuePort``. Si la PoC C-03 exige
RabbitMQ+Celery o Redis, se crea un nuevo adaptador equivalente y se selecciona
por la env var ``MESSAGING_BACKEND`` sin tocar dominio ni aplicacion.

NOTA C-04: la tabla de cola y las queries concretas son scope de C-05 (necesitan
el esquema). Aqui dejamos el esqueleto del adaptador con el contrato cumplido.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage


class PostgresMessageQueue(MessageQueuePort):
    """Cola sobre Postgres (SKIP LOCKED + LISTEN/NOTIFY). Default A4."""

    def __init__(self, dsn: str) -> None:
        # El pool real de conexiones se cablea en C-05 junto al esquema.
        self._dsn = dsn

    async def enqueue(self, topic: str, payload: dict[str, Any]) -> str:
        raise NotImplementedError(
            "La tabla de cola y el INSERT se implementan en C-05 (necesitan el esquema)."
        )

    async def dequeue(self, topic: str) -> QueuedMessage | None:
        raise NotImplementedError(
            "El SELECT ... FOR UPDATE SKIP LOCKED se implementa en C-05."
        )

    async def ack(self, message_id: str) -> None:
        raise NotImplementedError("El ack/DELETE se implementa en C-05.")

    async def health_check(self) -> bool:
        # En C-04 no hay pool aun; el smoke real de DB vive en los tests de
        # conectividad (5.3). Reportamos False explicito hasta cablear el pool.
        return False
