# C-03 — Resultados interinos: baseline en 4 cores (NO es el veredicto del pico)

> **Estado**: PARCIAL. El veredicto de arquitectura del concern (c) se evalúa SOLO
> en el pico E6 (~2.100 VU / ~5.000 ev/s) y **requiere un host de 8+ cores reales**
> (ver §"Por qué falta el veredicto"). Este documento registra lo medido en el host
> disponible (GitHub Codespaces **4 cores** / 16 GB, sin tarjeta) — útil para
> dimensionar, NO para decidir A4 vs SAD.

## Entorno

- Host: GitHub Codespaces `standardLinux32gb` = **4 cores / 16 GB**. Devcontainer
  reproducible en `.devcontainer/devcontainer.json`.
- Stack: multi-instancia A4 — 3× FastAPI mono-hilo (`api`/`api2`/`api3`, DD-10) tras
  `nginx-poc` round-robin **sin sticky**, Postgres+TimescaleDB, backplane
  LISTEN/NOTIFY. Bootstrap: `poc/bootstrap.sh`.
- Carga: `poc/k6/students.js` (WS, heartbeat 5 s + evento 1 s por VU).
- Medición fan-out: `poc/panels_asyncio.py`, **20 paneles SSE sobre 1 exam_id**,
  delta end-to-end `ts_backend → ts_rx`, p99 por ventana de 10 s.

## 1. Circuito multi-instancia: VALIDADO ✅

A 100 VU: ingesta `poc_ack_ok` 99.18 %, y los 20 paneles (repartidos por nginx sin
sticky entre las 3 instancias) reciben eventos de estudiantes conectados a OTRAS
instancias. **Eso solo es posible porque el backplane es Postgres (no memoria local).**
Concern (b) transporte panel y (c) backplane — el **circuito** — funcionalmente
demostrados. A4 **no refutado**.

## 2. La DB NO es el cuello ✅

`pgbench` directo contra Postgres, 32 clientes concurrentes, insert+commit durable
(`synchronous_commit=on`, `fsync=on`):

| Métrica | Valor |
|---|---|
| latencia media | **2,56 ms** |
| throughput | **12.504 tps** |

La DB hace **12.5k commits durables/s**; la carga del pico son ~5.000 ev/s. El
INSERT del evento es limpio (la hypertable `evento` **no tiene trigger**; el hash
encadenado vive en `audit_log`, otra tabla). Disco/fsync/DB descartados como cuello.

## 3. Límite de estudiantes simultáneos en 4 cores

Barrido de VUs (= estudiantes WS concurrentes), p99 fan-out estable por ventana:

| VU (estudiantes) | p99 fan-out | acks | SLO p99 < 500 ms |
|---|---|---|---|
| 20 | ~360–420 ms | 100 % | ✅ |
| **25** | **~455–475 ms** | 100 % | ✅ **(límite limpio)** |
| 30 | ~570–640 ms | 100 % | ❌ |
| 35 | ~740–860 ms | 100 % | ❌ |
| 40 | ~1.080–1.350 ms | 100 % | ❌ |
| 60 | ~1.000–1.500 ms | 100 % | ❌ |
| 80 | ~1.010–1.110 ms | 99.79 % | ❌ |
| 100 | ~1.000–1.370 ms | 99.18 % | ❌ |

**Límite limpio: ~25–30 estudiantes simultáneos** en 4 cores. El knee es abrupto
(saturación de CPU de golpe entre 25 y 30 VU).

### Control: el número de paneles NO mueve el límite (hipótesis refutada)

Se repitió el barrido con **3 paneles** (carga de observación realista: 1–3 revisores
por examen) para testear si los 20 paneles inflaban la latencia. **No la inflan:**

| VU | p99 con 3 paneles | p99 con 20 paneles |
|---|---|---|
| 40 | ~660–1.025 ms | ~1.080–1.350 ms |
| 60 | ~1.310–1.700 ms | ~1.000–1.500 ms |
| 80 | ~930–1.000 ms | ~1.010–1.110 ms |
| 100 | ~880–915 ms | ~1.000–1.370 ms |

Con 3 o con 20 paneles la latencia es ~la misma. **El cuello NO es el ancho del
fan-out SSE — es el event-loop del lado del estudiante** (persistir + `pg_notify` bajo
la carga WS), que es idéntico tengas 3 o 20 paneles mirando. → El límite de ~25–30
estudiantes **no depende del número de revisores**. (Hipótesis previa "20 paneles
inflan, el límite real es más alto" → **REFUTADA por el dato**.)

### Caveats (leer SÍ o SÍ antes de citar el número)

1. **El cuello es CPU/event-loop, no la arquitectura**: el `persist_latency` p99 era
   478 ms a 100 VU mientras la DB respondía en 2,5 ms. El tiempo se va en la corutina
   esperando CPU (3 FastAPI mono-hilo + Postgres + k6 + nginx + medidor peleando 4
   cores).
2. **Caja oversuscripta**: 3 instancias FastAPI + Postgres + nginx + k6 + medidor sobre
   **4 cores** = mucho más procesos que cores. La eficiencia por-core en producción
   (cada instancia con cores dedicados) sería **mayor** que la medida acá. Por eso este
   número NO se extrapola linealmente (ver §Dimensionamiento).
3. **La ingesta escala más que el fan-out en latencia, pero el ack roundtrip aguanta**:
   los acks se mantuvieron 100 % hasta 80 VU (99.57 % a 100). El sistema SIGUE
   funcionando a 100 VU (persiste, acka, entrega) — lo que se degrada es la **latencia**
   de fan-out, no la corrección.

## Dimensionamiento (lo honesto: NO alcanza para un modelo confiable)

La tentación es `2.100 / 27 ≈ 78 cajas de 4 cores`. **Eso sería el error de extrapolación
lineal que la regla #4 prohíbe**, por dos motivos:
- La caja de 4 cores está **oversuscripta** → subestima la eficiencia por-core real.
- El `NotifyQueueLock` de LISTEN/NOTIFY quiebra **no-linealmente** a ~5.000 NOTIFY/s, un
  régimen **inalcanzable** en 4 cores → el techo de la arquitectura está **sin medir**.

Lo único defendible hoy: **la DB no es el límite** (12.5k tps), **el cuello es CPU**
(escala con cores + réplicas horizontales), y **A4 no está refutado**. El número de
sizing para 1.000/2.100 **requiere el barrido limpio en 8+ cores** — sin eso, cualquier
cifra de "N cores para producción" es humo.

## Por qué falta el veredicto (y qué falta exactamente)

El riesgo #1 del concern (c) es el `NotifyQueueLock` global de Postgres en cada commit
de NOTIFY, que **recién** se vuelve cuello a ~5.000 ev/s (pico). En 4 cores la app
(event loops) satura **antes** de llegar a ese régimen → es imposible estresar el
backplane y ver si A4 quiebra. El veredicto E6 requiere:

- Host **8+ cores reales** (institucional / representativo de prod; NO Codespaces sin
  tarjeta, que topa en 4).
- Re-seed a ~2.200 sesiones (`SESSIONS=2200 bash poc/bootstrap.sh`) — a 2.100 VU con
  100 sesiones habría ~21 VU por `session_id` (irreal, pega contra locks por-sesión).
- Barrido E1→E6 según `poc/README.md`, criterio de aceptación SOLO en E6.

## Bug de producción destapado (arreglado)

`backend/pyproject.toml` no tenía driver sync para Alembic en las deps de runtime
(`psycopg[binary]` v3 estaba solo en el extra `dev`, que `pip install .` no instala) →
`ModuleNotFoundError: psycopg2` al migrar en entorno fresco. Fix: `psycopg2-binary` a
las deps principales. Commit `4cd32de`.
