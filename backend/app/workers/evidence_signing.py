"""Worker de firma maestra + re-inferencia de evidencia (C-12, etapas 3/4).

Consume tareas del topic ``evidence.sign`` de ``MessageQueuePort`` (la cola ganadora
de C-03 detras del puerto: Postgres-como-cola o RabbitMQ+Celery, indistinto para el
dominio). Por cada tarea ejecuta ``EvidenceSigningWorker.procesar`` (3.a verificacion
de hash + firma maestra asimetrica de Vault + re-inferencia server-side firmada).

El SLO E2->E4 < 30 s (p99) se instrumenta midiendo el tiempo desde el encolado hasta
el output firmado (Prometheus); aqui el loop solo orquesta el consumo. Cero perdida
(RN-CC-08): el ack solo se confirma tras persistir la firma; si el worker cae antes,
la tarea se vuelve a entregar y la cadena se completa al reprocesar (idempotente: las
columnas ya fijadas no se reescriben — trigger 0003).
"""

from __future__ import annotations

from app.application.evidence.service import (
    TOPIC_FIRMA_EVIDENCIA,
    EvidenceSigningWorker,
)
from app.infrastructure.messaging.port import MessageQueuePort


async def consumir_una(
    cola: MessageQueuePort, worker: EvidenceSigningWorker
) -> bool:
    """Reclama y procesa una tarea de firma de la cola. Devuelve ``True`` si proceso
    una; ``False`` si la cola estaba vacia. El ack se confirma SOLO tras la firma."""
    mensaje = await cola.dequeue(TOPIC_FIRMA_EVIDENCIA)
    if mensaje is None:
        return False
    await worker.procesar(mensaje.payload)
    await cola.ack(mensaje.id)
    return True
