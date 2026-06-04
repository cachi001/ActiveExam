# PoC C-03 — Harness de carga (DESCARTABLE)

> **ESTE CODIGO ES DESCARTABLE.** Nada de lo que vive en `poc/` se promueve a
> produccion. El entregable del change C-03 no es este codigo sino el
> **veredicto por concern** documentado. C-04…C-15 re-implementan el ganador
> con calidad de produccion. Ver `openspec/changes/c-03-poc-carga-mensajeria/design.md`.

## Proposito

Medir si la arquitectura A4 (Postgres-como-cola + SSE + LISTEN/NOTIFY) sostiene
el fan-out evento→panel con p99 < 500 ms al pico de ~2.100 VU / ~5.000 inserts/s.
La pieza SAD (Redis Pub/Sub, RabbitMQ+Celery) entra SOLO en el concern que falle
su SLO — no por defecto (DD-19).

## Tres concerns a medir

| Concern | Default A4 | Alternativa SAD | SLO |
|---------|------------|-----------------|-----|
| (a) Cola de trabajos | Postgres SKIP LOCKED | RabbitMQ + Celery | p99 < 30 s |
| (b) Transporte panel | SSE + backplane | WebSocket + sticky | reconexion < 5 s |
| **(c) Backplane** ⚠️ riesgo #1 | **LISTEN/NOTIFY** | **Redis Pub/Sub** | **p99 < 500 ms** |

El concern (c) es el riesgo #1: `LISTEN/NOTIFY` tiene un `NotifyQueueLock` global
en cada commit de `NOTIFY`. A ~5.000 eventos/s puede volverse el cuello de botella.

## Payload de NOTIFY (limite 8 KB)

El payload de `pg_notify` contiene SOLO el `event_id` (UUID, ~36 bytes) — muy
por debajo del limite de 8 KB de Postgres. El panel SSE resuelve el detalle del
evento contra la DB si necesita mas campos. Esto garantiza que ningun NOTIFY sea
rechazado silenciosamente por tamano de payload.

## Como levantar el stack PoC

```bash
# Desde la raiz del repo:
docker compose \
  -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.poc.yml \
  up -d
```

El override `docker-compose.poc.yml`:
- Excluye Keycloak (reemplazado por stub que duerme).
- Agrega env vars PoC al servicio `api` (POC_JWT_SECRET, POC_PANEL_ENABLED=1, POC_STUB_VAULT=1).
- Expone el puerto 8000 directamente (sin Nginx/TLS) para k6.

## Escalones del barrido (concern c — Bloque 5)

| Escalon | VU | Inserts/s aprox | Duracion minima |
|---------|----|-----------------|-----------------|
| P0 sanidad | 100 | ~50 | 5 min |
| E1 | 200 | ~200 | 3 min |
| E2 | 400 | ~400 | 3 min |
| E3 | 800 | ~1.000 | 3 min |
| E4 | 1.200 | ~2.000 | 3 min |
| E5 | 1.600 | ~3.500 | 3 min |
| **E6 pico** | **2.100** | **~5.000** | **≥ 10 min (criterio)** |
| E7 quiebre | rampa > 2.100 | > 5.000 | hasta romper |

El criterio de aceptacion se evalua SOLO en E6 (pico). P0 y E1–E5 son sanidad
y validacion del escalado ~lineal (SU-06), no son criterio de aceptacion.

## Estructura de directorios

```
poc/
  README.md          # este archivo
  k6/
    seed.py          # crea sesiones con clave HMAC conocida en la DB (Bloque 4)
    students.js      # generador de carga WS (Bloque 4)
    evidence.js      # generador de evidencia (Bloque 4)
  panels_asyncio.py  # 20-40 conexiones SSE simultaneas, mide p99 (Bloque 4)
```

## Endpoint SSE del panel (Bloque 1)

```
GET /poc/panel/stream?exam_id={exam_id}
Content-Type: text/event-stream

data: {"event_id": "...", "ts_backend": "2026-06-03T12:34:56.123456+00:00", "ts_rx": "..."}\n\n
```

Disponible SOLO cuando `POC_PANEL_ENABLED=1`. En produccion esta var es `False`
y el router no se monta.

## Verificar que el circuito funciona (sin Docker)

```bash
# Desde psql conectado a la DB, suscribirse al canal:
LISTEN "panel:exam-uuid-aqui";

# Desde otro cliente, mandar un evento WS con k6 o directamente con curl
# al endpoint de ingestion. Ver ts_backend con microsegundos en el NOTIFY.
```
