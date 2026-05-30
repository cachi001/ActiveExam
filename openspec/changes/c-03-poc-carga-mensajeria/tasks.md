# Tasks — C-03 `poc-carga-mensajeria`

> **Naturaleza**: estas tareas construyen un **harness de carga descartable** y producen un **veredicto por concern por métrica**. El Done de cada tarea de medición es **un número leído de Prometheus/Tempo contra un umbral del `14`**, no una feature entregada. El change se completa solo cuando los tres veredictos (a, b, c) están registrados; recién ahí se desbloquea C-04 con la infraestructura decidida.
> Convención: `(Métrica: <umbral>)` indica el criterio de aceptación medido.

## 1. Montar el harness y la instrumentación (capability `load-poc-harness`)

- [ ] 1.1 Levantar el entorno de la PoC (2–3 instancias FastAPI mono-hilo tras Nginx, PostgreSQL/TimescaleDB, Redis y RabbitMQ disponibles para swap por concern); Done: stack arriba y conectado
- [ ] 1.2 Montar la instrumentación ANTES de cargar: Prometheus (p50/p95/p99 por concern, profundidad de cola, lag de backplane, inserts/s, conexiones/instancia), Tempo (traza evento→persist→fan-out→panel), dashboard Grafana de la PoC (DD-12); Done: métricas y trazas visibles sin generar carga aún (Métrica: instrumentación completa pre-carga)
- [ ] 1.3 Construir el generador de estudiantes: ~2.100 conexiones WS sintéticas con heartbeat firmado /5s (~200 inserts/s) + eventos normales (~1.000 inserts/s) + ráfaga multi-examen (~5.000 inserts/s pico); Done: generador calibrado contra el capacity model del `14`
- [ ] 1.4 Construir el generador de paneles: N=20–40 suscriptores sintéticos (≈ 1 proctor/50–100 estudiantes), cada uno suscripto a sus sesiones, midiendo timestamp de recepción evento→panel; Done: latencia de propagación instrumentada por panel
- [ ] 1.5 Construir el generador de evidencia: uploads sintéticos que encolan re-inferencia+firma; Done: cola alimentada bajo carga
- [ ] 1.6 Definir los perfiles de tráfico P0 (reposo, sanidad), P1 (sostenido ~1.000), P2 (pico ~2.100/~5.000, criterio), P3 (punto de quiebre), P4 (caos); Done: perfiles parametrizados y reproducibles
- [ ] 1.7 Declarar explícitamente en el README de la PoC que el código es descartable y que el entregable es la decisión; Done: naturaleza descartable documentada

## 2. Validar capacity model y suposición de escalado (capability `load-poc-harness`)

- [ ] 2.1 Correr P0 (reposo) para validar la sanidad del harness y la instrumentación; Done: el harness reporta métricas coherentes (no es criterio de aceptación)
- [ ] 2.2 Correr P1 (sostenido ~1.000 conc. / ~1.000 inserts/s) y registrar el comportamiento base; Done: sostenido confirmado
- [ ] 2.3 Escalar P1→P2 y registrar si el escalado de inserts es ~lineal (valida o refuta SU-06); Done: Suposición de escalado documentada (Métrica: lineal sostenido→pico ✓/✗)

## 3. Concern (a) — Cola de trabajos asíncrona (capability `job-queue-validation`)

- [ ] 3.1 Correr P2 con la cola en **Postgres** (`SKIP LOCKED` + pg-boss/`LISTEN/NOTIFY`); medir p99 de re-inferencia+firma y profundidad de cola; Done: métricas registradas (Métrica: p99 < 30 s, cola acotada)
- [ ] 3.2 Correr P2 con la cola en **RabbitMQ quorum + Celery** bajo idéntico tráfico; medir las mismas métricas; Done: comparación apples-to-apples registrada
- [ ] 3.3 Aplicar la matriz de decisión y registrar el **veredicto del concern (a)**: conservar Postgres ✓ o promover RabbitMQ ✗, con la métrica que lo justifica; Done: veredicto (a) documentado

## 4. Concern (b) — Transporte del panel (capability `panel-transport-validation`)

- [ ] 4.1 Correr P2 con el panel sobre **SSE + backplane (sin sticky)**; durante la corrida, redistribuir/caer instancias FastAPI; medir continuidad de suscripción y reconexión; Done: comportamiento registrado (Métrica: sin pérdida de suscripción, reconexión transparente)
- [ ] 4.2 Correr P2 con el panel sobre **WebSocket + sticky sessions** bajo idéntico escenario; medir concentración de conexiones/instancia y comportamiento de reconexión; Done: comparación registrada
- [ ] 4.3 Aplicar la matriz y registrar el **veredicto del concern (b)**: conservar SSE ✓ o promover WebSocket+sticky ✗; Done: veredicto (b) documentado

## 5. Concern (c) — Backplane de eventos ⚠️ riesgo #1 (capability `realtime-backplane-validation`)

- [ ] 5.1 Correr P2 con el backplane sobre **Postgres `LISTEN/NOTIFY`** y 20–40 paneles activos EN SOSTENIDO AL PICO; medir p99 de propagación evento→panel; Done: p99 registrado (Métrica: p99 < 500 ms al pico)
- [ ] 5.2 Correr P2 con el backplane sobre **Redis Pub/Sub** bajo idéntico tráfico; medir el mismo p99; Done: comparación apples-to-apples registrada
- [ ] 5.3 Correr P3 (barrido creciente) degradando **`LISTEN/NOTIFY` hasta el punto de quiebre** donde p99 cruza 500 ms; registrar el throughput (eventos/s × N paneles) en ese punto vs el pico requerido; Done: punto de quiebre y margen registrados (Métrica: throughput de quiebre vs pico)
- [ ] 5.4 Correr P4 (caos): inyectar caída de instancia/nodo + reconexión de paneles durante P2 para ambas opciones; verificar exactly-once lógico por conteo extremo a extremo; Done: cero pérdida y cero duplicados verificados (Métrica: exactly-once bajo caos)
- [ ] 5.5 Registrar el **veredicto explícito del concern (c)**: `LISTEN/NOTIFY` sostiene el pico ✓ o se promueve Redis Pub/Sub ✗, con el punto de quiebre; Done: veredicto (c) documentado con la cota de migración

## 6. Registrar el veredicto de arquitectura y cerrar el gate (capability `architecture-verdict`)

- [ ] 6.1 Consolidar los tres veredictos (a, b, c), cada uno citando su métrica, umbral y decisión; Done: documento de veredicto por concern completo
- [ ] 6.2 Documentar toda promoción de pieza del SAD como evolución condicionada en el ADR (no retrabajo), respetando DD-19; Done: evolución documentada o constancia de "A4 conservado en los tres concerns"
- [ ] 6.3 Dejar el veredicto consumible por C-04 (infra), C-10 (fan-out), C-12 (cola de evidencia) y C-15 (transporte del panel); Done: qué cola/transporte/backplane se implementan, sin ambigüedad
- [ ] 6.4 Comunicar el cierre del gate y habilitar C-04; Done: gate de validación de arquitectura declarado cerrado y veredicto distribuido al equipo
