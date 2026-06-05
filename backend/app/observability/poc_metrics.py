"""Metricas Prometheus de la PoC C-03 (Bloque 2, DESCARTABLE).

Declara las tres metricas que sostienen la decision por concern del barrido de
carga (Bloque 5). Se DECLARAN aqui (no en produccion) porque el entregable de
C-03 es el veredicto, no este codigo; C-10/C-12/C-15 re-declaran las que el
ganador necesite con calidad de produccion.

Por que declararlas ANTES de generar carga (D5/D14): sin estas metricas, toda
decision de arquitectura seria sobre logs ad-hoc -- indefendible. Instanciar el
objeto basta para que aparezca en /metrics con valor 0 (sin carga); el .observe()
las llena durante el barrido.

Las tres metricas:
- ``fanout_latency_seconds``  (Histogram) -> concern (c): latencia evento->panel.
- ``evidence_signing_seconds`` (Histogram) -> concern (a): re-inferencia + firma.
- ``job_queue_depth``          (Gauge)     -> concern (a): profundidad de la cola.

Importar este modulo registra las tres en el REGISTRY por defecto de
prometheus_client, que es el que ``telemetry.metrics_endpoint()`` renderiza.
"""

from __future__ import annotations

from prometheus_client import Gauge, Histogram

# Concern (c) -- riesgo #1. Latencia del fan-out evento->panel (LISTEN/NOTIFY->SSE).
# SLO: p99 < 500 ms al pico ~2.100 VU. Buckets finos alrededor de la frontera de 0.5 s
# (legibilidad del p99 en la zona de aceptacion) + 0.025 en el piso (el backplane sano
# es ~31 ms: hay que distinguirlo por debajo de 50 ms) + cola hasta 10 s.
# El techo en 2.0 s era CIEGO: en B5.1 (host saturado) el p99 real >2 s leia "2000 ms"
# (cota del ultimo bucket) y la cola quedaba indistinguible. Extendido a 10 s.
fanout_latency_seconds = Histogram(
    "fanout_latency_seconds",
    "Latencia evento->panel (fan-out del backplane, concern c). SLO p99 < 0.5 s.",
    buckets=(0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Concern (a). Latencia de re-inferencia + firma de evidencia en el worker.
# SLO: p99 < 30 s. Buckets escalonados hasta 30 s (la frontera del SLO).
evidence_signing_seconds = Histogram(
    "evidence_signing_seconds",
    "Latencia re-inferencia + firma de evidencia (worker, concern a). SLO p99 < 30 s.",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# Concern (a). Profundidad instantanea de la cola Postgres de trabajos. El criterio
# es que quede ACOTADA (no crezca sin techo) al pico; el worker la actualiza.
job_queue_depth = Gauge(
    "job_queue_depth",
    "Profundidad instantanea de la cola Postgres de trabajos (concern a). Debe quedar acotada.",
)

# Concern (c) — DESCOMPOSICION del fan-out para no atribuir al backplane lo que es
# persistencia. fanout_latency_seconds (arriba) mide el TOTAL ts_backend->ts_rx; estas
# dos lo parten en sus dos tramos para localizar el cuello de botella real:
#   persist_latency_seconds  = ts_backend -> ts_publish (INSERT + commit a la hypertable)
#   backplane_latency_seconds= ts_publish -> ts_rx      (pg_notify + entrega SSE, A4 puro)
# Buckets identicos al fan-out (piso 0.025 para el backplane sano ~31 ms, cola a 10 s):
# en B5.1 ambos tramos superaron 2 s bajo saturacion y el techo viejo los hacia ilegibles.
persist_latency_seconds = Histogram(
    "persist_latency_seconds",
    "Latencia de persistencia evento (INSERT+commit hypertable) antes del fan-out (concern c).",
    buckets=(0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
)
backplane_latency_seconds = Histogram(
    "backplane_latency_seconds",
    "Latencia del backplane PURO (pg_notify->panel SSE), sin persistencia (concern c, A4).",
    buckets=(0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
)
