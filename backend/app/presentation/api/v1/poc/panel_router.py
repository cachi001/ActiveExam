"""Router SSE descartable del panel de proctores — PoC C-03 D9 (DESCARTABLE).

Cierra el circuito del concern (c): un evento WS del estudiante ->
``pg_notify('panel:{exam_id}', payload)`` -> este endpoint emite ``data: ...\n\n``
al proctor suscripto a ese exam_id.

Este router se monta SOLO cuando ``poc_panel_enabled=True`` (env var
``POC_PANEL_ENABLED=1``). En produccion esa var es False y el router nunca se
registra. El endpoint de produccion lo implementa C-15 con lifecycle completo.

CIRCUITO:
  k6/cliente  ->  WS /api/v1/events/ws  ->  ingestion.ingest()
            ->  backplane.publish(canal='panel:{exam_id}', payload)
            ->  AsyncpgPublisher.publish()  ->  pg_notify('panel:{exam_id}', '{"event_id":"..."}')
            ->  este endpoint (LISTEN 'panel:{exam_id}')  ->  SSE data: {...}

ENDPOINT:
  GET /poc/panel/stream?exam_id={exam_id}
  Content-Type: text/event-stream

  Emite por cada notificacion de Postgres:
    data: {"event_id": "...", "ts_backend": "...", "ts_rx": "..."}\n\n

  El cliente (panels_asyncio.py) calcula el delta ``ts_rx - ts_backend`` para
  medir la latencia de fan-out (concern c, SLO p99 < 500 ms).

DESCONEXION: cuando el cliente SSE desconecta (GeneratorExit o anyio.ClosedResourceError),
  el LISTEN se cancela y la conexion asyncpg se cierra ordenadamente.

ENTORNO WINDOWS / Docker Desktop:
  asyncpg puede fallar al resolver 'localhost'. El DSN usa '127.0.0.1' explicito
  (ver AsyncpgPublisher._dsn_asyncpg). Si esto falla, el endpoint devuelve 503
  con un mensaje de error claro.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

# Metrica de fan-out (Bloque 2): el endpoint observa aqui el delta ts_rx-ts_backend
# server-side, asi /metrics tiene el histograma del concern (c) durante el barrido.
# Import tolerante: si prometheus_client falta, el stream sigue funcionando sin medir.
try:
    from app.observability.poc_metrics import (
        backplane_latency_seconds,
        fanout_latency_seconds,
    )
except Exception:  # noqa: BLE001
    fanout_latency_seconds = None
    backplane_latency_seconds = None

_log = logging.getLogger(__name__)

router = APIRouter()


def _now_iso_us() -> str:
    """Timestamp UTC con microsegundos para ``ts_rx`` (PoC C-03 D11)."""
    return datetime.now(timezone.utc).isoformat()


@router.get("/panel/stream")
async def panel_sse_stream(
    request: Request,
    exam_id: str = Query(..., description="UUID del examen a observar."),
) -> StreamingResponse:
    """Stream SSE de eventos de un examen para el panel de proctores (PoC C-03).

    Abre una conexion asyncpg DEDICADA, ejecuta ``LISTEN panel:{exam_id}`` y
    emite un ``data:`` SSE por cada notificacion de Postgres.

    Uso desde curl (verificacion manual):
        curl -N "http://localhost:8000/poc/panel/stream?exam_id=<uuid>"

    Uso desde panels_asyncio.py (medicion de latencia):
        python poc/panels_asyncio.py --panels 20 --exam-ids <uuid1> <uuid2>
    """
    settings = getattr(request.app.state, "settings", None)
    database_url = getattr(settings, "database_url", None) if settings else None

    if not database_url:
        async def _error_gen():
            yield "data: {\"error\": \"database_url no configurado\"}\n\n"
        return StreamingResponse(_error_gen(), media_type="text/event-stream", status_code=503)

    canal = f"panel:{exam_id}"

    async def _event_generator():
        """Generador SSE: LISTEN -> emitir data: por cada NOTIFY -> cierre ordenado."""
        try:
            import asyncpg  # type: ignore[import-untyped]
        except ModuleNotFoundError:
            _log.error("panel_sse_stream: asyncpg no instalado.")
            yield 'data: {"error": "asyncpg no disponible"}\n\n'
            return

        # Convertir DSN SQLAlchemy a asyncpg puro + '127.0.0.1' (Windows/WSL2).
        from app.infrastructure.messaging.asyncpg_publisher import _dsn_asyncpg
        dsn = _dsn_asyncpg(database_url)

        conn = None
        _on_notify = None  # definido en el try; usado en finally para remove_listener
        try:
            conn = await asyncpg.connect(dsn)
            _log.info("panel_sse_stream: conexion abierta para exam_id=%s", exam_id)

            # Cola interna para transferir notificaciones al generador SSE.
            queue: asyncio.Queue[str] = asyncio.Queue()

            def _on_notify(_conn, _pid, channel, payload):  # type: ignore[misc]
                """Callback de asyncpg: se llama en el loop de asyncio."""
                queue.put_nowait(payload)

            await conn.add_listener(canal, _on_notify)
            _log.info("panel_sse_stream: LISTEN '%s' activo.", canal)

            # Emitir un comentario SSE inicial para confirmar que el stream esta vivo.
            yield f": conectado a {canal}\n\n"

            # Loop: esperar notificaciones y emitirlas como SSE.
            while True:
                # Verificar desconexion del cliente cada 1 s (polling ligero).
                try:
                    raw_payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Sin notificacion en 1 s: verificar si el cliente sigue conectado.
                    if await request.is_disconnected():
                        _log.info(
                            "panel_sse_stream: cliente desconectado (exam_id=%s).", exam_id
                        )
                        break
                    # Emitir heartbeat SSE para mantener la conexion viva.
                    yield ": keep-alive\n\n"
                    continue

                # Parsear el payload del NOTIFY (JSON minimo: {"event_id": "..."}).
                # Capturar el datetime de recepcion (no solo el string) para medir
                # el delta de fan-out sin re-parsear.
                ts_rx_dt = datetime.now(timezone.utc)
                ts_rx = ts_rx_dt.isoformat()
                try:
                    data = json.loads(raw_payload)
                except (json.JSONDecodeError, ValueError):
                    # Payload no es JSON valido: emitir crudo con ts_rx.
                    data = {"raw": raw_payload}

                # Observar la latencia de fan-out (concern c, Bloque 2): delta entre
                # ts_backend (emision, del payload) y ts_rx (recepcion en el panel).
                # Defensivo: payload sin ts_backend valido -> no se observa, no rompe.
                ts_backend_str = data.get("ts_backend") if isinstance(data, dict) else None
                ts_publish_str = data.get("ts_publish") if isinstance(data, dict) else None
                # Total ts_backend->ts_rx (persist + backplane).
                if fanout_latency_seconds is not None and ts_backend_str:
                    try:
                        ts_backend_dt = datetime.fromisoformat(str(ts_backend_str).replace("Z", "+00:00"))
                        delta_s = (ts_rx_dt - ts_backend_dt).total_seconds()
                        if delta_s >= 0:
                            fanout_latency_seconds.observe(delta_s)
                    except (ValueError, TypeError):
                        pass
                # Backplane PURO ts_publish->ts_rx (pg_notify + SSE, sin persistencia).
                if backplane_latency_seconds is not None and ts_publish_str:
                    try:
                        ts_publish_dt = datetime.fromisoformat(str(ts_publish_str).replace("Z", "+00:00"))
                        bp_s = (ts_rx_dt - ts_publish_dt).total_seconds()
                        if bp_s >= 0:
                            backplane_latency_seconds.observe(bp_s)
                    except (ValueError, TypeError):
                        pass

                # Agregar ts_rx para que el cliente mida el delta con ts_backend.
                data["ts_rx"] = ts_rx

                sse_line = f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
                yield sse_line

        except Exception as exc:  # noqa: BLE001
            _log.error(
                "panel_sse_stream: error en el generador SSE (exam_id=%s): %s",
                exam_id,
                exc,
            )
            yield f'data: {{"error": "{exc}"}}\n\n'
        finally:
            # Cierre ordenado: quitar el listener y cerrar la conexion asyncpg.
            if conn is not None:
                if _on_notify is not None:
                    try:
                        await conn.remove_listener(canal, _on_notify)
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    await conn.close()
                except Exception:  # noqa: BLE001
                    pass
            _log.info("panel_sse_stream: conexion asyncpg cerrada (exam_id=%s).", exam_id)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            # Cache-Control: no-cache es requerido por el protocolo SSE.
            "Cache-Control": "no-cache",
            # X-Accel-Buffering: off desactiva el buffering de Nginx para SSE.
            "X-Accel-Buffering": "no",
        },
    )


class PocEnqueueRequest(BaseModel):
    """Cuerpo de ``POST /poc/enqueue``: evidencia sintética para el concern (a)."""

    model_config = ConfigDict(extra="forbid")  # regla dura: rechaza campos no declarados

    session_id: str | None = None
    blob_size: int = 1024


@router.post("/enqueue")
async def poc_enqueue(request: Request, body: PocEnqueueRequest) -> dict:
    """Encola UN job de evidencia sintética en ``poc_job_queue`` (PoC C-03, concern a).

    Alternativa descartable al endpoint real ``/evidence/notify`` (que re-descarga el
    binario de WORM + valida firma): mide la cola Postgres bajo carga HTTP concurrente
    sin el peso del flujo de custodia. El worker PoC (``poc_load_worker``) la drena.

    Lo alimenta ``evidence.js`` (k6). Disponible solo con ``poc_panel_enabled=True``.
    """
    from app.infrastructure.messaging.poc_postgres_queue import TOPIC_POC_EVIDENCIA
    from app.observability import poc_metrics

    cola = getattr(request.app.state, "poc_queue", None)
    if cola is None:
        raise HTTPException(status_code=503, detail="cola PoC no cableada (poc_queue=None)")

    payload = {"session_id": body.session_id, "blob": "x" * max(0, body.blob_size)}
    job_id = await cola.enqueue(TOPIC_POC_EVIDENCIA, payload)
    depth = await cola.depth(TOPIC_POC_EVIDENCIA)
    poc_metrics.job_queue_depth.set(depth)
    return {"enqueued": True, "job_id": job_id, "depth": depth}
