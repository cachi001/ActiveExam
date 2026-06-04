"""Cola Postgres de la PoC C-03 (Bloque 3, DESCARTABLE).

Adaptador de ``MessageQueuePort`` sobre la tabla ``poc_job_queue`` (migracion 0006),
para medir el concern (a): reclamo concurrente con ``FOR UPDATE SKIP LOCKED``.

AISLAMIENTO PoC/prod: NO toca ``PostgresMessageQueue`` (el adaptador de produccion,
C-05, que apunta a otra tabla). Esta clase es un adaptador PARALELO descartable; el
worker PoC y, en el barrido, el endpoint de ingesta la inyectan en vez del de prod.
C-05 implementa el de produccion con el esquema real; aqui solo se mide.

CONEXION: lazy, unica y reutilizada (suficiente para el worker consumidor y para
verificar el loop). NOTA para el Bloque 5: bajo carga (~2.100 VU) el enqueue desde
multiples requests necesitaria un POOL — una sola conexion serializa los INSERT y
falsearia la medicion. Cablear asyncpg.create_pool antes del barrido del concern (a).

Este modulo es DESCARTABLE: C-05 re-implementa la cola de produccion con lifecycle
completo, pool supervisado y el esquema real.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.messaging.asyncpg_publisher import _dsn_asyncpg
from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage

_log = logging.getLogger(__name__)

try:
    import asyncpg  # type: ignore[import-untyped]
    _ASYNCPG_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]
    _ASYNCPG_AVAILABLE = False


# Reclamo atomico FIFO: selecciona la fila pendiente mas antigua del topic con
# SKIP LOCKED (no espera a filas bloqueadas por otros workers) y la marca tomada
# en el mismo statement. Devuelve id/topic/payload del job reclamado.
_SQL_DEQUEUE = """
WITH siguiente AS (
    SELECT id
    FROM poc_job_queue
    WHERE topic = $1 AND taken_at IS NULL
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE poc_job_queue q
SET taken_at = now()
FROM siguiente
WHERE q.id = siguiente.id
RETURNING q.id, q.topic, q.payload;
"""


class PocPostgresQueue(MessageQueuePort):
    """Cola Postgres descartable (SKIP LOCKED) sobre ``poc_job_queue`` (PoC C-03)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = _dsn_asyncpg(dsn)
        self._conn: Any | None = None  # asyncpg.Connection | None

    async def _ensure_connection(self) -> Any:
        if not _ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg no esta instalado (cola PoC C-03 deshabilitada).")
        if self._conn is None or self._conn.is_closed():
            self._conn = await asyncpg.connect(self._dsn)
        return self._conn

    async def enqueue(self, topic: str, payload: dict[str, Any]) -> str:
        """INSERT en ``poc_job_queue``. Devuelve el id (UUID) como str."""
        conn = await self._ensure_connection()
        row = await conn.fetchrow(
            "INSERT INTO poc_job_queue (topic, payload) VALUES ($1, $2::jsonb) RETURNING id",
            topic,
            json.dumps(payload, separators=(",", ":")),
        )
        return str(row["id"])

    async def dequeue(self, topic: str) -> QueuedMessage | None:
        """Reclama el siguiente job pendiente del ``topic`` (FOR UPDATE SKIP LOCKED)."""
        conn = await self._ensure_connection()
        row = await conn.fetchrow(_SQL_DEQUEUE, topic)
        if row is None:
            return None
        # payload es JSONB -> asyncpg lo devuelve como str; deserializar a dict.
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return QueuedMessage(id=str(row["id"]), topic=row["topic"], payload=payload)

    async def ack(self, message_id: str) -> None:
        """Confirma el procesamiento: DELETE de la fila (job completado)."""
        conn = await self._ensure_connection()
        await conn.execute("DELETE FROM poc_job_queue WHERE id = $1::uuid", message_id)

    async def health_check(self) -> bool:
        try:
            conn = await self._ensure_connection()
            await conn.execute("SELECT 1")
            return True
        except Exception as exc:  # noqa: BLE001
            _log.warning("PocPostgresQueue health_check fallo: %s", exc)
            return False

    async def depth(self, topic: str) -> int:
        """Profundidad de la cola (jobs pendientes) — para ``job_queue_depth`` (Bloque 2)."""
        conn = await self._ensure_connection()
        row = await conn.fetchrow(
            "SELECT count(*) AS n FROM poc_job_queue WHERE topic = $1 AND taken_at IS NULL",
            topic,
        )
        return int(row["n"]) if row else 0

    async def close(self) -> None:
        if self._conn is not None and not self._conn.is_closed():
            await self._conn.close()
        self._conn = None
