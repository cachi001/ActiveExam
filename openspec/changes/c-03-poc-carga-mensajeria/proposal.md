# Proposal — C-03 `poc-carga-mensajeria`

> **Naturaleza del change**: PoC de carga formal de Fase 0, governance **CRÍTICO**, **★ Tier 1 · BLOQUEANTE**. Su entregable **NO es código de producción** sino **la decisión de arquitectura** documentada por métrica. El código de la PoC es un **prototipo descartable**. Sin esta decisión, nada de cola / transporte / tiempo real (C-04, C-10, C-12, C-15) puede avanzar.

## Why

El proyecto arrastra dos inconsistencias estructurales sin resolver (IN-01, IN-02) y un principio rector que prohíbe resolverlas por opinión: **DD-19** — "empezá con la arquitectura más simple que cumpla los NFR, instrumentá todo, y agregá complejidad solo cuando una métrica lo demuestre necesario". El SAD original (cap. 7–9) propone un stack de mensajería de tres piezas (RabbitMQ quorum + Celery + Redis) y WebSocket+sticky en todos los canales; el análisis A4 (DD-15, DD-16) sostiene que para esta escala eso está **sobre-dimensionado** y propone Postgres-como-cola + SSE+backplane con `LISTEN/NOTIFY`.

La hipótesis por defecto es A4 (lo simple). Pero **la simplicidad no se asume: se gana con una métrica**. El NFR de capacidad se endureció (SU-06): de 700 a **1.000 concurrentes sostenido / ~2.100 pico / ~5.000 inserts/s**. Y hay un riesgo de tiempo real concreto y bien identificado: `LISTEN/NOTIFY` **serializa el fan-out por una conexión y toma un lock global en el commit del `NOTIFY`**; a ~1.000–5.000 eventos/s entre instancias puede no sostener el SLO de propagación al panel (p99 < 500 ms del `14`). Ese es el concern con **mayor probabilidad de promover la pieza del SAD** (Redis Pub/Sub).

Este change valida la arquitectura **bajo carga real al pico**, antes de construir nada encima, para que C-04…C-16 se levanten sobre una decisión medida y no sobre una apuesta. Es el gate que transforma "creemos que A4 alcanza" en "medimos que A4 alcanza (o no, y por eso promovemos X)".

## What Changes

Este change **no produce software de producción**. Construye un **harness de carga descartable** y produce un **veredicto por concern**. La decisión NO es binaria SAD-vs-A4: se descompone en **tres concerns independientes** que se validan por separado y pueden tener veredictos distintos.

- **Concern (a) — Cola de trabajos** (re-inferencia + firma de evidencia, camino **asíncrono**, presupuesto **< 30 s**, NO tiempo real): **Postgres-como-cola** (pg-boss / `SKIP LOCKED` + `LISTEN/NOTIFY`) **vs** **RabbitMQ quorum + Celery**. Hipótesis default = Postgres (A4, DD-15, IN-01).
- **Concern (b) — Transporte del panel** (tiempo real, sub-500 ms): **SSE + backplane (sin sticky)** **vs** **WebSocket + sticky sessions**. Hipótesis default = SSE (A4, DD-16, IN-02). El canal del **estudiante** se queda en **WebSocket bidireccional** aparte y **no está bajo decisión** en este change.
- **Concern (c) — Backplane de eventos** (el **riesgo de tiempo real #1**): **Postgres `LISTEN/NOTIFY`** **vs** **Redis Pub/Sub**. Hipótesis default = `LISTEN/NOTIFY` (A4, DD-16). Es el concern con mayor probabilidad de promover Redis: el criterio de fan-out al pico decide aquí.

**Criterio de aceptación clavado al PICO (NO al sostenido)** — ~2.100 concurrentes / ~5.000 inserts/s, con los SLO del `14`:

- **Tiempo real — fan-out del panel**: con **N paneles de proctor activos** (≈ 1 proctor / 50–100 estudiantes ⇒ **~20–40 paneles concurrentes**) suscriptos a sus sesiones asignadas, la propagación evento→panel debe ser **p99 < 500 ms EN SOSTENIDO AL PICO** (no en reposo). **Este criterio decide `LISTEN/NOTIFY` vs Redis.**
- **Cero pérdida** de eventos confirmados / evidencia: **exactly-once lógico** bajo reconexión y caída de instancia.
- **Re-inferencia + firma final < 30 s** desde la subida (asíncrono, no tiempo real).
- Generadores de carga contrastados contra el **capacity model** del `14`; **instrumentación completa** (Prometheus / Tempo) para decidir **por métrica, no por opinión**.
- **Salida por concern**: decisión registrada — promover la pieza del SAD **solo si la métrica lo exige**; documentada como **evolución, no retrabajo**. Veredicto explícito del backplane: `LISTEN/NOTIFY` sostiene el pico ✓ / se promueve Redis ✗.

**BREAKING (gate)**: hasta que el veredicto por concern esté registrado, **C-04 y todo lo de cola/transporte/tiempo real (C-10, C-12, C-15) no pueden iniciar** — no sabrían qué infraestructura levantar. Es un bloqueo deliberado.

## Capabilities

> Estas capabilities modelan **criterios de validación de carga verificables por métrica**, no comportamiento de software de producción. Cada requisito SHALL se prueba ejecutando el harness al pico y leyendo Prometheus/Tempo; su Done es un número medido contra un umbral, no una feature entregada.

### New Capabilities

- `load-poc-harness`: el harness de carga descartable — generadores de tráfico al pico (~2.100 conc. / ~5.000 inserts/s), perfiles de tráfico, paneles sintéticos, e instrumentación completa (Prometheus/Tempo) para que toda decisión sea por métrica.
- `job-queue-validation` (Concern a): validación de la cola de trabajos asíncrona — Postgres-como-cola vs RabbitMQ+Celery — contra el presupuesto de re-inferencia + firma **< 30 s** al pico.
- `panel-transport-validation` (Concern b): validación del transporte del panel — SSE+backplane (sin sticky) vs WebSocket+sticky — bajo caída/redistribución de instancias sin pérdida de suscripción.
- `realtime-backplane-validation` (Concern c): validación del backplane de eventos — `LISTEN/NOTIFY` vs Redis Pub/Sub — contra el SLO de fan-out **p99 < 500 ms al pico sostenido con N paneles activos**, incluyendo el punto de quiebre de `LISTEN/NOTIFY`.
- `architecture-verdict`: el registro de la decisión por concern — qué pieza queda en el MVP, qué métrica lo justifica, y el veredicto explícito del backplane (sostiene ✓ / se promueve ✗) como evolución documentada, no retrabajo.

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. Las capabilities de C-01/C-02 son de governance y no se tocan. -->

(Ninguna — este change no modifica requisitos de capacidades existentes; el código que valida es descartable y no se promueve a `openspec/specs/`.)

## Impact

- **Bloquea**: C-04 (foundation-setup) y, por transitividad, todo lo de cola/transporte/tiempo real — C-10 (event-ingestion-transport), C-12 (evidencia-cadena-custodia, usa el ganador de cola), C-15 (panel-proctor-sse, usa el ganador de transporte/backplane).
- **Dependencias entrantes**: `C-01` (ADRs/DPIA aprobados — congela la hipótesis A4 que esta PoC pone a prueba) y `C-02` (designación de revisores). Ambos son gates de Fase 0; corren en paralelo entre sí.
- **Decisiones que produce** (consumidas downstream):
  - Concern (a) → qué cola levanta C-04 e implementa C-12.
  - Concern (b) → qué transporte de panel implementa C-15.
  - Concern (c) → qué backplane implementan C-10 (fan-out) y C-15 (alertas < 500 ms).
- **Relación con C-01**: C-01 **congela la hipótesis** A4 como contrato de arquitectura; C-03 la **valida o la refuta con métrica**. Si C-03 promueve una pieza del SAD, queda como **evolución condicionada documentada en el ADR**, no como contradicción ni retrabajo.
- **Actores/sistemas afectados**: equipo técnico (ejecuta la PoC y recibe el veredicto), patrocinador (avala la decisión de gastar/no gastar complejidad operacional). No afecta código de dominio ni infraestructura de producción todavía.
- **Riesgo principal validado**: que `LISTEN/NOTIFY` no sostenga el fan-out al pico (riesgo de tiempo real #1). La PoC lo ataca **de frente**, degradándolo hasta el punto de quiebre.
