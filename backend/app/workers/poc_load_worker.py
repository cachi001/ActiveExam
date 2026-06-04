"""Worker de carga de la PoC C-03 (Bloque 3, DESCARTABLE).

Consume jobs de ``poc_job_queue`` (via ``PocPostgresQueue``) y simula el trabajo del
worker de evidencia con STUBS de latencia fija (sin Vault ni MediaPipe): el objetivo
es medir el concern (a) -- profundidad de cola y latencia de firma bajo carga -- no
ejecutar la firma real. C-12 corre el worker real (``app.workers.evidence_signing``).

LATENCIAS STUB (bajo ``poc_stub_vault=True``):
- re-inferencia server-side: ~400 ms (``asyncio.sleep``)
- firma maestra (Vault):     ~200 ms (``asyncio.sleep``)
Total ~600 ms/job: muy por debajo del SLO p99 < 30 s, pero suficiente para que la
cola se acumule bajo carga y ``job_queue_depth`` sea medible.

INSTRUMENTACION (Bloque 2): por cada job procesado observa ``evidence_signing_seconds``
(tiempo dequeue->ack) y actualiza ``job_queue_depth`` (jobs pendientes en la cola).

USO (dentro del contenedor api):
    python -m app.workers.poc_load_worker --enqueue 5   # siembra 5 jobs de prueba
    python -m app.workers.poc_load_worker --drain        # procesa hasta vaciar y sale
    python -m app.workers.poc_load_worker --forever      # loop continuo (barrido B5)

Este modulo es DESCARTABLE.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from app.config import get_settings
from app.infrastructure.messaging.poc_postgres_queue import PocPostgresQueue
from app.observability import poc_metrics

_log = logging.getLogger(__name__)

# Topic propio de la PoC (aislado del TOPIC_FIRMA_EVIDENCIA de produccion).
TOPIC_POC = "poc.evidence.sign"

# Latencias stub (segundos). Activas solo si poc_stub_vault=True.
LAT_INFERENCE_S = 0.4
LAT_SIGNER_S = 0.2

# Pausa del loop --forever cuando la cola esta vacia (evita busy-spin).
_IDLE_SLEEP_S = 0.2


async def _stub_reinferencia(activo: bool) -> None:
    """Simula la re-inferencia server-side (DD-17) sin MediaPipe."""
    if activo:
        await asyncio.sleep(LAT_INFERENCE_S)


async def _stub_firma_maestra(activo: bool) -> None:
    """Simula la firma maestra asimetrica (Vault) sin tocar Vault."""
    if activo:
        await asyncio.sleep(LAT_SIGNER_S)


async def procesar_uno(cola: PocPostgresQueue, *, stub_vault: bool) -> bool:
    """Reclama y procesa un job. Devuelve True si proceso uno; False si la cola
    estaba vacia. El ack se confirma SOLO tras los stubs (cero perdida, RN-CC-08)."""
    mensaje = await cola.dequeue(TOPIC_POC)
    if mensaje is None:
        return False

    t0 = time.monotonic()
    await _stub_reinferencia(stub_vault)   # etapa 4 (re-inferencia)
    await _stub_firma_maestra(stub_vault)  # etapa 3 (firma maestra)
    await cola.ack(mensaje.id)
    elapsed = time.monotonic() - t0

    # Instrumentacion del concern (a): latencia de firma + profundidad de cola.
    poc_metrics.evidence_signing_seconds.observe(elapsed)
    poc_metrics.job_queue_depth.set(await cola.depth(TOPIC_POC))
    return True


async def _enqueue_n(cola: PocPostgresQueue, n: int) -> None:
    """Siembra ``n`` jobs sinteticos en la cola (para verificar el loop sin endpoint)."""
    for i in range(n):
        await cola.enqueue(TOPIC_POC, {"job": i, "blob": "evidencia-sintetica"})
    poc_metrics.job_queue_depth.set(await cola.depth(TOPIC_POC))
    _log.info("PoC worker: %d jobs encolados en '%s'.", n, TOPIC_POC)


async def _drain(cola: PocPostgresQueue, *, stub_vault: bool) -> int:
    """Procesa hasta vaciar la cola. Devuelve cuantos jobs proceso."""
    procesados = 0
    while await procesar_uno(cola, stub_vault=stub_vault):
        procesados += 1
    _log.info("PoC worker: drain completo, %d jobs procesados.", procesados)
    return procesados


async def _forever(cola: PocPostgresQueue, *, stub_vault: bool, metrics_port: int) -> None:
    """Loop continuo de consumo (para el barrido del Bloque 5).

    Expone su PROPIO /metrics: las metricas Prometheus son in-memory por proceso, y el
    worker es un proceso distinto del uvicorn que sirve /metrics del api. Prometheus
    scrapea AMBOS (api y worker) por separado. Sin esto, evidence_signing_seconds y
    job_queue_depth observadas por el worker no serian visibles.
    """
    from prometheus_client import start_http_server

    start_http_server(metrics_port)
    _log.info(
        "PoC worker: /metrics en :%d, loop --forever iniciado (topic '%s').",
        metrics_port,
        TOPIC_POC,
    )
    while True:
        if not await procesar_uno(cola, stub_vault=stub_vault):
            await asyncio.sleep(_IDLE_SLEEP_S)


async def _main(args: argparse.Namespace) -> None:
    settings = get_settings()
    cola = PocPostgresQueue(dsn=settings.database_url)
    try:
        if args.enqueue:
            await _enqueue_n(cola, args.enqueue)
        elif args.forever:
            await _forever(
                cola, stub_vault=settings.poc_stub_vault, metrics_port=args.metrics_port
            )
        else:  # --drain (default)
            await _drain(cola, stub_vault=settings.poc_stub_vault)
    finally:
        await cola.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Worker de carga PoC C-03 (descartable).")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--enqueue", type=int, metavar="N", help="Siembra N jobs y sale.")
    grupo.add_argument("--drain", action="store_true", help="Procesa hasta vaciar y sale (default).")
    grupo.add_argument("--forever", action="store_true", help="Loop continuo (barrido B5).")
    parser.add_argument(
        "--metrics-port", type=int, default=9100, help="Puerto /metrics del worker (--forever)."
    )
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
