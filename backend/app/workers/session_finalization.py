"""Worker de consolidacion del score al cierre de sesion (C-13, tarea asincrona, D5).

Consume tareas del topic ``session.finalize`` de ``MessageQueuePort`` (cola ganadora
de C-03 detras del puerto). Por cada tarea ejecuta
``SessionFinalizationService.consolidar``: recomputa el score final (idempotente),
libera la clave de sesion y decide el encolado por umbral (flaggeada/archivada).

El ack se confirma SOLO tras consolidar; si el worker cae antes, la tarea se vuelve a
entregar y la consolidacion (idempotente, recomputable desde la hypertable) produce
el mismo resultado sin doble conteo (RN-SC-04). El score PRIORIZA, NUNCA sanciona.
"""

from __future__ import annotations

from app.application.scoring.finalization import (
    TOPIC_CIERRE_SESION,
    SessionFinalizationService,
)
from app.infrastructure.messaging.port import MessageQueuePort


async def consumir_una(
    cola: MessageQueuePort, service: SessionFinalizationService
) -> bool:
    """Reclama y consolida una tarea de cierre. Devuelve ``True`` si proceso una;
    ``False`` si la cola estaba vacia. El ack se confirma solo tras consolidar."""
    mensaje = await cola.dequeue(TOPIC_CIERRE_SESION)
    if mensaje is None:
        return False
    await service.consolidar(str(mensaje.payload["session_id"]))
    await cola.ack(mensaje.id)
    return True
