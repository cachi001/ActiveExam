"""Instrumentacion Prometheus minima para main_activeexam.py.

`main_activeexam.py` es deliberadamente liviano (sin OTel/Tempo, ver su
docstring), pero hoy no expone NINGUNA metrica real — ni siquiera latencia o
throughput HTTP. Esto se detecto al intentar medir una prueba de carga: no
habia forma de ver, desde Prometheus/Grafana, como responde el backend bajo
concurrencia (solo se podia medir desde afuera, con el cliente de carga).

Este modulo agrega lo minimo para que la carga sea observable:
  - Histogram de latencia HTTP por metodo+path+status.
  - Counter de requests HTTP por metodo+path+status.
  - `/metrics` expone esas metricas MAS las de proceso que prometheus_client
    registra automaticamente (process_cpu_seconds_total,
    process_resident_memory_bytes) — CPU y memoria del proceso sin código
    adicional.

No agrega OTel ni trazas: eso pertenece a `app.observability.telemetry`
(stack "full"), que main_activeexam.py explicitamente no usa.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total de requests HTTP procesados",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latencia de requests HTTP",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def _template_path(request: Request) -> str:
    """Path con placeholders (`/sessions/{id}`) en vez del id real, para no
    explotar la cardinalidad de la metrica con un valor por sesion."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if path is not None else request.url.path


def instrument_activeexam_metrics(app: FastAPI) -> None:
    """Cablea el middleware de metricas HTTP y el endpoint `/metrics`."""

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = _template_path(request)
        http_requests_total.labels(
            method=request.method, path=path, status=str(response.status_code)
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method, path=path
        ).observe(duration)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def _metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
