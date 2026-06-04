# Tasks — C-03 `poc-carga-mensajeria`

> **Naturaleza**: estas tareas construyen un **harness de carga descartable** y producen un **veredicto por concern por métrica**. El código de la PoC vive en `poc/` (descartable) y en cambios mínimos de `backend/` marcados como PoC; nada se promueve a producción. El entregable del change NO es código sino el **veredicto por concern** documentado. El change se completa solo cuando los tres veredictos (a, b, c) están registrados; recién ahí se desbloquea C-04 con la infraestructura decidida.
>
> **Enfoque**: medir A4 primero (DD-19). Se construye y mide solo el stack A4 (Postgres-como-cola + SSE + Postgres LISTEN/NOTIFY). La pieza SAD entra **solo en el concern que falle** su SLO. El orden de ejecución es: concern (c) primero — riesgo #1 — luego (a) y (b).
>
> Convención: `(Métrica: <umbral>)` indica el criterio de aceptación medido.

## Bloque 0 — Infra y modo sin-auth PoC

> **Esfuerzo**: S. **Objetivo**: levantar el stack A4 mínimo sin Keycloak, verificar que todos los servicios responden, y declarar las vars PoC en Settings sin romper el stack de producción.

- [x] 0.1 Agregar vars PoC opcionales a `backend/app/config.py` → `poc_jwt_secret: Optional[str] = None`, `poc_panel_enabled: bool = False`, `poc_stub_vault: bool = False`; respetar `extra='forbid'` de Pydantic; Done: `python -c "from app.config import Settings; Settings()"` no lanza error con y sin las vars seteadas
- [x] 0.2 Crear `docker-compose.poc.yml` (override) que excluye Keycloak, expone PostgreSQL + Redis (disponible para swap posterior) + FastAPI + Prometheus + Grafana; Done: `docker compose -f docker-compose.yml -f docker-compose.poc.yml up -d` levanta sin error
- [x] 0.3 Implementar middleware PoC de auth HS256: si `poc_jwt_secret` está seteado, aceptar tokens firmados con HS256 estático (`build_hs256_verify` ya existe en `verifiers.py`); bypass de Keycloak solo cuando `poc_panel_enabled=True`; Done: request con token HS256 estático pasa auth y llega al handler
- [x] 0.4 Verificar stack completo arriba: FastAPI `/health` responde 200, PostgreSQL conectado, Prometheus scrapea métricas del backend; Done: stack A4 sin Keycloak operativo end-to-end

## Bloque 1 — Publisher asyncpg + panel SSE descartable

> **Esfuerzo**: M. **Objetivo**: cerrar el circuito completo del concern (c): WS estudiante → evento → `pg_notify` real → panel SSE recibe. Hito verificable: un solo k6 VU manda 1 evento WS → el NOTIFY se ejecuta → el panel SSE lo recibe y registra `ts_rx`. Este bloque es **precondición** del Bloque 5 (medición concern c).

- [x] 1.1 Verificar límite de payload NOTIFY: confirmar que el payload de `pg_notify` contiene solo `event_id` (UUID, ~36 bytes, bien bajo el límite de 8 KB de Postgres); documentar en README de la PoC; Done: payload verificado y documentado
- [x] 1.2 Implementar publisher asyncpg real en `backend/app/infrastructure/messaging/backplane.py`: `backplane.publish()` hoy delega en `app.state.backplane_publisher` que es `None` (fan-out no-op inerte); implementar el publisher que ejecuta `EXECUTE pg_notify(canal, payload)` con conexión asyncpg dedicada; Done: `pg_notify` ejecutado al recibir un evento WS (verificable con `LISTEN` en `psql`)
- [x] 1.3 Fix `_now_iso()` en `channel.py`: cambiar de `datetime.strftime('%Y-%m-%dT%H:%M:%SZ')` (trunca a segundos) a `datetime.now(timezone.utc).isoformat()` (microsegundos); Done: timestamp tiene precisión de microsegundos — **CRÍTICO para medir sub-500 ms** (sin este fix el error de medición es ±1.000 ms)
- [x] 1.4 Construir endpoint SSE descartable `GET /poc/panel/stream?exam_id={exam_id}` en un router PoC: abre conexión asyncpg dedicada, ejecuta `LISTEN panel:{exam_id}`, emite `text/event-stream` con cada notificación, registra `ts_rx` en el payload; Done: endpoint devuelve `Content-Type: text/event-stream` y emite eventos (verificable con `curl`)
- [x] 1.5 Verificar el circuito completo E2E: k6 manda 1 evento WS → FastAPI procesa → publisher ejecuta `pg_notify` → panel SSE recibe y loguea el delta `ts_emit - ts_rx`; Done: delta visible en logs del panel SSE — **hito de circuito cerrado**

## Bloque 2 — Instrumentación Prometheus

> **Esfuerzo**: S. **Objetivo**: declarar y exponer las métricas necesarias para los 3 concerns ANTES de generar carga (D5/D14). Sin estas métricas toda decisión sería sobre logs ad-hoc — indefendible.

- [x] 2.1 Declarar `fanout_latency_seconds` (Histogram, buckets 0.05/0.1/0.2/0.5/1.0/2.0 s) — mide latencia evento→panel para concern (c); Done: métrica visible en `/metrics` sin carga — **VERIFICADO en vivo**: declarada en `observability/poc_metrics.py`, visible en `/metrics` en 0, y observando real (count=1, sum=0.0014 s tras 1 NOTIFY) vía `.observe()` en el panel SSE
- [x] 2.2 Declarar `evidence_signing_seconds` (Histogram, buckets 0.5/1/2/5/10/30 s) — mide latencia re-inferencia+firma para concern (a); Done: métrica visible en `/metrics` — **VERIFICADO**: visible en `/metrics` con sus 6 buckets en 0. El `.observe()` lo cablea el worker (Bloque 3)
- [x] 2.3 Declarar `job_queue_depth` (Gauge) — mide profundidad de la cola de trabajos; Done: métrica visible en `/metrics` y actualizada por el worker — **VERIFICADO (parcial)**: declarada y visible en `/metrics` (= 0). La actualización (`.set()`) la hace el worker del Bloque 3 (task 3.7), aún no construido
- [ ] 2.4 Importar dashboard Grafana PoC con paneles por concern: p99 fan-out (concern c), p99 signing (concern a), queue_depth (concern a), inserts/s, conexiones/instancia; Done: dashboard importado y visible con datos reales al correr P0 — **PENDIENTE**: su Done exige datos reales de P0 (Bloque 5); se hace tras el barrido

## Bloque 3 — Cola Postgres mínima + worker ejecutable

> **Esfuerzo**: M. **Objetivo**: implementar la cola Postgres funcional (sin `NotImplementedError`) y un worker ejecutable con stubs de Vault/inferencia, para que concern (a) pueda medirse de forma aislada.

- [x] 3.1 Crear migración Alembic para tabla `poc_job_queue` (id UUID PK, payload JSONB, created_at TIMESTAMPTZ, taken_at TIMESTAMPTZ nullable); Done: migración aplicada sin error — **VERIFICADO**: `migrations/versions/0006_poc_job_queue.py` (branch independiente `down_revision=None`, como 0005 slim), `alembic upgrade 0006` → `Running upgrade -> 0006`. ⚠️ GAP: `psycopg2` no está en la imagen (Alembic lo necesita); se instaló en runtime para la PoC — pendiente agregarlo a requirements para el Bloque 5
- [x] 3.2 Implementar `enqueue()` — `INSERT INTO poc_job_queue`; Done: enqueue funcional — **VERIFICADO**: `--enqueue 5` → `SELECT count(*)` = 5. **DECISIÓN DE DISEÑO**: implementado en adaptador PoC descartable `poc_postgres_queue.py` (NO en el `postgres_queue.py` de producción), para no ensuciar prod con SQL de `poc_job_queue` — mantiene el aislamiento PoC/prod
- [x] 3.3 Implementar `dequeue()` — `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1` con `taken_at = now()`; Done: dequeue funcional sin conflictos entre workers — **VERIFICADO**: `--drain` procesó los 5 (CTE atómico reclamo+marca)
- [x] 3.4 Implementar `ack()` — `DELETE FROM poc_job_queue WHERE id = $1`; Done: ack funcional — **VERIFICADO**: `SELECT count(*)` = 0 tras el drain
- [x] 3.5 Stub de firma maestra: si `poc_stub_vault=True`, latencia fija (~200 ms) sin Vault; Done: **VERIFICADO** (inline en el worker: `_stub_firma_maestra`, 0.2 s)
- [x] 3.6 Stub de re-inferencia: si `poc_stub_vault=True`, latencia fija (~400 ms) sin MediaPipe; Done: **VERIFICADO** (inline en el worker: `_stub_reinferencia`, 0.4 s)
- [x] 3.7 Verificar loop de worker: dequeue → stub inferencia → stub firma → ack → `evidence_signing_seconds.observe()`; Done: worker procesa jobs con `job_queue_depth` en Prometheus — **VERIFICADO en /metrics del worker (:9100)**: `evidence_signing_seconds_count=5`, `sum=3.047` (~0.61 s/job = 0.4+0.2), `job_queue_depth=0`. NOTA: el worker expone su PROPIO /metrics (métricas in-memory por proceso); en B5 Prometheus scrapea api y worker por separado

## Bloque 4 — Scripts k6 + seed + panel asyncio

> **Esfuerzo**: M. **Objetivo**: construir los generadores de carga descartables calibrados contra el capacity model. Todo el código vive en `poc/` y NO se promueve a producción.

- [ ] 4.1 Crear `poc/k6/seed.py`: crea N sesiones de examen con clave HMAC conocida en la DB (para que k6 pueda firmar los eventos correctamente); Done: script crea sesiones y las lista por stdout
- [ ] 4.2 Crear `poc/k6/students.js`: VU parametrizable que abre conexión WS, envía heartbeat firmado HMAC cada 5 s (~200 inserts/s @ 100 VU) + eventos normales; parámetro `VU_COUNT` configurable; Done: script ejecuta con `k6 run --vus 100 --duration 60s poc/k6/students.js` sin errores
- [ ] 4.3 Crear `poc/k6/evidence.js`: VU que sube evidencia sintética (blob pequeño) al endpoint de ingesta, encolando re-inferencia; Done: script alimenta la cola con `job_queue_depth > 0` visible en Prometheus
- [ ] 4.4 Crear `poc/panels_asyncio.py`: abre N=20–40 conexiones SSE simultáneas con asyncio + `httpx`, cada una a `/poc/panel/stream?exam_id=X`; registra `ts_rx` local y calcula delta con `ts_emit` del payload; imprime p50/p95/p99 por ventana de 10 s; Done: script ejecuta con `python poc/panels_asyncio.py --panels 20 --exam-ids ...` y reporta percentiles
- [ ] 4.5 Definir y documentar los escalones del barrido en `poc/README.md`: 100 → 200 → 400 → 800 → 1.200 → 1.600 → 2.100 VU, con duración mínima de 3 min por escalón; Done: escalones documentados y reproducibles

## Bloque 5 — Barrido A4 y medición de los 3 SLO

> **Esfuerzo**: M. **Objetivo**: medir el stack A4 completo en los 3 concerns, empezando por (c) — el riesgo #1. Para cada concern: si A4 cumple el SLO → veredicto inmediato sin construir SAD.

### P0 — Sanidad del harness (precondición de todo)

- [ ] 5.1 Correr P0 (100 VU, 5 min): verificar que el harness reporta métricas coherentes y el circuito E2E funciona; Done: Prometheus muestra `fanout_latency_seconds`, `evidence_signing_seconds` y `job_queue_depth` con valores reales — NO es criterio de aceptación, es sanidad

### Concern (c) — Backplane LISTEN/NOTIFY — riesgo #1

- [ ] 5.2 Correr barrido de escalones sobre concern (c) con backplane `LISTEN/NOTIFY` y N=20 paneles SSE activos: 100 → 200 → 400 → 800 → 1.200 → 1.600 → 2.100 VU; registrar p99 de `fanout_latency_seconds` en cada escalón; Done: curva p99 por escalón registrada
- [ ] 5.3 Identificar el punto de quiebre del concern (c): escalón donde p99 cruza 500 ms; si el quiebre está por encima de 2.100 VU → A4 sostiene con margen; Done: punto de quiebre documentado en eventos/s (Métrica: umbral p99 < 500 ms al pico ~2.100 VU)
- [ ] 5.4 Registrar veredicto preliminar del concern (c) A4: `LISTEN/NOTIFY` sostiene ✓ si p99 < 500 ms a 2.100 VU con margen; pendiente de fallo → pasa a Bloque 6(c); Done: veredicto preliminary (c) documentado con el punto de quiebre y el margen

### Concern (a) — Cola Postgres asíncrona

- [ ] 5.5 Correr barrido de escalones sobre concern (a) con Postgres-cola (`SKIP LOCKED`) y worker con stubs: 100 → 400 → 1.200 → 2.100 VU; registrar p99 de `evidence_signing_seconds` y `job_queue_depth` en cada escalón; Done: métricas registradas por escalón
- [ ] 5.6 Registrar veredicto preliminar del concern (a) A4: cola Postgres conservada ✓ si p99 < 30 s y `job_queue_depth` acotado (no crece sin techo) a 2.100 VU; pendiente de fallo → pasa a Bloque 6(a); Done: veredicto preliminary (a) documentado (Métrica: p99 < 30 s, cola acotada)

### Concern (b) — Transporte SSE del panel bajo redistribución

- [ ] 5.7 Correr P2 (2.100 VU, ≥ 10 min) sobre concern (b) con SSE + backplane sin sticky: durante la corrida, bajar y subir una instancia FastAPI; verificar que los paneles SSE reconectan automáticamente y no pierden suscripción; Done: comportamiento registrado (Métrica: sin pérdida de suscripción, reconexión transparente < 5 s)
- [ ] 5.8 Registrar veredicto preliminar del concern (b) A4: SSE conservado ✓ si reconexión es transparente y sin pérdida de suscripción; pendiente de fallo → pasa a Bloque 6(b); Done: veredicto preliminary (b) documentado

### Validación de SU-06 (escalado lineal)

- [ ] 5.9 Con los datos de la curva del barrido, registrar si el escalado de inserts sostenido → pico es ~lineal o no-lineal; Done: Suposición SU-06 confirmada o refutada con la curva real (Métrica: lineal ✓/✗ con el factor medido)

## Bloque 6 — Comparar SAD SOLO en el concern que falle + veredicto final

> **Esfuerzo**: S/M condicional — se ejecuta ÚNICAMENTE en los concerns cuyo veredicto preliminary A4 fue ✗. Si todos los concerns pasan A4, este bloque se documenta como "no ejecutado — A4 sostuvo los 3 concerns" y el change cierra directamente. El código SAD es también descartable (poc/).

### Concern (c) — Redis Pub/Sub (solo si LISTEN/NOTIFY falló en 5.3–5.4)

- [ ] 6.1 [CONDICIONAL — solo si 5.4 = ✗] Implementar adaptador Redis Pub/Sub descartable en `poc/` como swap del backplane A4; Done: adaptador funcional como reemplazo del publisher asyncpg
- [ ] 6.2 [CONDICIONAL] Repetir barrido de escalones con Redis Pub/Sub y N=20 paneles SSE bajo idéntico tráfico; registrar p99 de `fanout_latency_seconds`; Done: curva p99 Redis registrada (Métrica: p99 < 500 ms al pico ~2.100 VU)
- [ ] 6.3 [CONDICIONAL] Registrar veredicto final del concern (c): comparar punto de quiebre `LISTEN/NOTIFY` vs Redis; documentar la decisión con ambos números; Done: veredicto (c) final — `LISTEN/NOTIFY` ✓ o Redis promovido ✗ — con el punto de quiebre de ambas opciones

### Concern (a) — RabbitMQ + Celery (solo si Postgres-cola falló en 5.5–5.6)

- [ ] 6.4 [CONDICIONAL — solo si 5.6 = ✗] Levantar RabbitMQ quorum + Celery en el `docker-compose.poc.yml`; implementar adapter descartable en `poc/`; Done: worker Celery procesa jobs del mismo workload
- [ ] 6.5 [CONDICIONAL] Correr barrido de escalones con RabbitMQ + Celery bajo idéntico tráfico; registrar p99 y profundidad de cola; Done: comparación apples-to-apples registrada (Métrica: p99 < 30 s, cola acotada)
- [ ] 6.6 [CONDICIONAL] Registrar veredicto final del concern (a): Postgres-cola ✓ o RabbitMQ promovido ✗; Done: veredicto (a) final con métrica que lo justifica

### Concern (b) — WebSocket + sticky (solo si SSE falló en 5.7–5.8)

- [ ] 6.7 [CONDICIONAL — solo si 5.8 = ✗] Configurar sticky sessions en Nginx + WebSocket de panel descartable en `poc/`; Done: panel WS+sticky funcional bajo redistribución
- [ ] 6.8 [CONDICIONAL] Correr P2 con WS+sticky bajo idéntico escenario de redistribución; registrar reconexión y pérdida de suscripción; Done: comparación registrada
- [ ] 6.9 [CONDICIONAL] Registrar veredicto final del concern (b): SSE ✓ o WS+sticky promovido ✗; Done: veredicto (b) final con métrica que lo justifica

### Veredicto consolidado y cierre del gate

- [ ] 6.10 Consolidar los tres veredictos (a, b, c) — cada uno citando su métrica medida, el umbral, y la decisión (A4 conservado / SAD promovido) — en el documento de veredicto de arquitectura; Done: documento de veredicto completo, consumible por C-04/C-10/C-12/C-15
- [ ] 6.11 Documentar toda promoción de pieza del SAD como evolución condicionada en el ADR correspondiente (respetando DD-19); si A4 sostuvo los 3 concerns, documentar "A4 conservado en los 3 concerns" con la cota de migración del backplane; Done: ADR actualizado o constancia de conservación
- [ ] 6.12 Comunicar el cierre del gate: veredicto por concern disponible para C-04 (infra), C-10 (fan-out), C-12 (cola de evidencia) y C-15 (transporte del panel) — sin ambigüedad sobre qué cola, transporte y backplane se implementan; Done: gate declarado cerrado
