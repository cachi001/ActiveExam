# Design — C-03 `poc-carga-mensajeria`

> **Aclaración de naturaleza**: este SÍ es un design técnico, pero de un **prototipo descartable**, no de software de producción. Documenta el **harness de la PoC** (generadores de carga, perfiles de tráfico al pico, instrumentación), la **matriz de decisión por concern** (qué métrica promueve qué pieza del SAD) y el **punto de quiebre esperado del backplane**. El entregable del change NO es este código sino el **veredicto por concern** que produce. Nada de lo que se construye aquí se promueve a producción; C-04…C-15 re-implementan el ganador con calidad de producción.

## Context

El proyecto Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO + Prometheus/Loki/Tempo/Grafana) tiene un NFR de capacidad endurecido (SU-06, `14`): **1.000 concurrentes sostenido / ~2.100 pico multi-examen / ~5.000 inserts/s en pico**. El discovery dejó dos inconsistencias sin resolver y un principio que prohíbe resolverlas por opinión:

- **IN-01**: SAD = RabbitMQ+Celery+Redis (3 piezas) vs A4 = Postgres-como-cola (1 pieza). Afecta costo operacional, número de piezas a operar y time-to-market.
- **IN-02**: SAD = WebSocket+sticky en todo vs A4 = SSE+backplane para el panel (sin sticky).
- **DD-19** (principio rector): simplicidad primero, instrumentar todo, complejidad **solo por métrica**. La validación se hace con esta PoC.

**El riesgo de tiempo real #1** está identificado con precisión técnica: Postgres `LISTEN/NOTIFY` **serializa el fan-out por una única conexión** y **toma un lock global (`NotifyQueueLock`) en el commit de cada `NOTIFY`**. A bajo volumen es invisible; a ~1.000–5.000 eventos/s de fan-out entre instancias, ese lock y la cola de notificaciones de 8 KB pueden volverse el cuello de botella y romper el SLO de propagación. Redis Pub/Sub (sub-50 ms, diseñado para fan-out) es la pieza del SAD candidata a promoverse **si y solo si** la métrica lo exige.

**Constraints**:
- El criterio se clava al **PICO (~2.100 / ~5.000 inserts/s), NO al sostenido**. Medir en reposo o solo en sostenido invalidaría la decisión.
- La métrica de tiempo real se mide **EN SOSTENIDO AL PICO**, no en un burst aislado ni en estado de reposo del sistema.
- El escalado ~lineal de inserts respecto del sostenido es una **Suposición** (SU-06) que la PoC debe validar, no asumir.
- No promover piezas del SAD por defecto: la carga de la prueba la lleva quien quiera agregar complejidad (DD-19).
- El código es **descartable**: optimizar para velocidad de medición y fidelidad del perfil de tráfico, no para mantenibilidad de producción.

**Stakeholders**: equipo técnico (ejecuta y decide), patrocinador (avala el costo operacional de la decisión), receptores downstream (C-04 infra, C-10 ingesta/fan-out, C-12 cola de evidencia, C-15 panel).

## Goals / Non-Goals

**Goals:**
- Medir, al **pico** (~2.100 conc. / ~5.000 inserts/s), las tres opciones default de A4 y sus alternativas del SAD, **concern por concern**.
- Producir un **veredicto por concern** justificado por una métrica contra un umbral del `14`, no por opinión.
- **Atacar de frente** el backplane: degradar `LISTEN/NOTIFY` hasta su **punto de quiebre** y determinar si sostiene **p99 < 500 ms de fan-out con N paneles activos en sostenido al pico**.
- Validar **cero pérdida** (exactly-once lógico) bajo reconexión y caída de instancia (caos).
- Validar **re-inferencia + firma < 30 s** al pico para la cola asíncrona.
- Validar la **Suposición** de escalado ~lineal de inserts (SU-06).
- Dejar la decisión documentada como **evolución condicionada**, no como retrabajo.

**Non-Goals:**
- NO construir software de producción: el harness es descartable; C-04…C-15 re-implementan el ganador.
- NO validar el canal **WebSocket del estudiante** como decisión (es bidireccional y no está en disputa; se modela solo como **generador de carga** que produce los inserts).
- NO decidir el motor de visión, el esquema de eventos definitivo, ni los umbrales de score (otros changes).
- NO promover ningún ganador a `openspec/specs/` — este change no deja specs de dominio.
- NO probar burst aislados como criterio: el criterio es **sostenido al pico**.

## Decisions

### D1 — Descomponer la decisión en 3 concerns independientes, no en un binario SAD-vs-A4
**Decisión**: validar por separado **(a) cola de trabajos**, **(b) transporte del panel** y **(c) backplane de eventos**; cada uno puede tener un veredicto distinto.
**Por qué**: son problemas con perfiles de carga, SLOs y modos de falla diferentes. La cola es asíncrona (< 30 s); el backplane es tiempo real (< 500 ms). Mezclarlos llevaría a "promover RabbitMQ porque el panel va lento", que es una falacia. Aislar cada concern permite promover **solo** la pieza que la métrica exige.
**Alternativa considerada**: decisión binaria SAD vs A4 → promovería tres piezas por culpa de una; viola DD-19.

### D2 — Clavar el criterio al PICO, medido en sostenido al pico (no en reposo, no en burst)
**Decisión**: todo SLO se evalúa a ~2.100 concurrentes / ~5.000 inserts/s, con el sistema **sostenido en ese pico** durante una ventana de medición (mín. 10 min), no en un burst instantáneo ni en reposo.
**Por qué**: el SLO de panel (< 500 ms) que decide el backplane se rompe precisamente cuando el sistema está saturado, no cuando está ocioso. Medir en reposo daría un falso ✓ a `LISTEN/NOTIFY`.
**Alternativa considerada**: medir al sostenido (1.000) → subdimensiona; el pico multi-examen es el escenario real de riesgo (SU-06).

### D3 — Atacar el backplane de frente: degradar `LISTEN/NOTIFY` hasta el punto de quiebre
**Decisión**: no basta con un ✓/✗ binario al pico; barrer la carga de fan-out (eventos/s × N paneles) **hasta encontrar el punto de quiebre** donde p99 cruza 500 ms, y compararlo contra el pico requerido.
**Por qué**: el margen importa. Si `LISTEN/NOTIFY` sostiene el pico pero rompe al 110%, no hay headroom y el veredicto debe reflejarlo. Conocer el punto de quiebre convierte la decisión en defendible y da la cota de cuándo migrar a Redis en producción.
**Alternativa considerada**: solo medir ✓/✗ al pico exacto → no da margen ni cota de evolución.

### D4 — El ganador NO se promueve a producción; el entregable es el veredicto
**Decisión**: el código del harness es descartable; C-04…C-15 re-implementan el ganador con calidad de producción. Este change deja un **documento de veredicto por concern**, no código reutilizable.
**Por qué**: una PoC optimizada para medir rápido y degradar componentes no tiene la calidad (tests, seguridad, manejo de errores) de producción. Promover su código sería deuda técnica disfrazada.
**Alternativa considerada**: evolucionar la PoC a producción → arrastra atajos de la PoC al MVP.

### D5 — Decisión por métrica leída de Prometheus/Tempo, no por inspección ad-hoc
**Decisión**: toda aceptación se evalúa leyendo percentiles de Prometheus y trazas distribuidas de Tempo (DD-12), con la instrumentación montada **antes** de generar carga.
**Por qué**: "una función no observable no está lista" (DD-12). Una decisión de arquitectura tomada sobre `print`s o impresiones no es defendible ante el patrocinador.
**Alternativa considerada**: medir con logs ad-hoc → no reproducible, no auditable.

## Arquitectura del harness (prototipo descartable)

```
┌─────────────────────────────────────────────────────────────────────┐
│  GENERADORES DE CARGA (descartables)                                 │
│                                                                       │
│  [gen-estudiantes] ~2.100 conexiones WS sintéticas                    │
│     ├─ heartbeat firmado /5s        → ~200 inserts/s sostenido        │
│     ├─ eventos normales              → ~1.000 inserts/s sostenido      │
│     └─ ráfaga multi-examen           → picos hasta ~5.000 inserts/s    │
│                                                                       │
│  [gen-paneles] N=20–40 suscriptores SSE/WS (proctores sintéticos)     │
│     └─ cada uno suscripto a sus sesiones asignadas; mide t_evento→t_rx │
│                                                                       │
│  [gen-evidencia] uploads sintéticos → encola re-inferencia+firma      │
└───────────────┬───────────────────────────────────────────────────────┘
                │
        ┌───────▼─────────┐      ┌──────────────────────────────────────┐
        │ FastAPI (2–3     │      │  CONCERN (c) BACKPLANE (swap A/B)     │
        │ instancias)      │─────►│  A: Postgres LISTEN/NOTIFY            │
        │ ingesta + fan-out│◄─────│  B: Redis Pub/Sub                    │
        └───────┬──────────┘      └──────────────────────────────────────┘
                │                  ┌──────────────────────────────────────┐
                │  CONCERN (a)     │  A: Postgres-cola (SKIP LOCKED+pgboss)│
                ├─ cola ──────────►│  B: RabbitMQ quorum + Celery         │
                │                  └──────────────────────────────────────┘
                │  CONCERN (b)     ┌──────────────────────────────────────┐
                └─ transporte ────►│  A: SSE + backplane (sin sticky)     │
                                   │  B: WebSocket + sticky sessions      │
                                   └──────────────────────────────────────┘
                │
        ┌───────▼──────────┐   ┌─────────────────────────────────────────┐
        │ PostgreSQL/      │   │ INSTRUMENTACIÓN (montada ANTES de cargar)│
        │ TimescaleDB      │   │  Prometheus: p50/p95/p99 por concern,    │
        │ (hypertable)     │   │   profundidad de cola, lag de backplane, │
        └──────────────────┘   │   inserts/s, conexiones/instancia        │
                               │  Tempo: traza evento→persist→fan-out→panel│
                               │  Grafana: dashboard de la PoC por concern│
                               └─────────────────────────────────────────┘
```

Cada concern se prueba con **A** (default A4) y **B** (alternativa SAD) en corridas separadas, mismo perfil de tráfico, mismo capacity model, swap del adaptador. Comparación apples-to-apples.

### Perfiles de tráfico (del capacity model, `14`)

| Perfil | Concurrentes | Inserts/s | N paneles | Duración | Qué valida |
|--------|--------------|-----------|-----------|----------|------------|
| P0 baseline (reposo) | ~100 | ~50 | 5 | 5 min | Sanidad del harness; NO es criterio de aceptación |
| P1 sostenido | ~1.000 | ~1.000 | 10–20 | 15 min | Confirma capacity sostenido (SU-06) |
| **P2 pico (criterio)** | **~2.100** | **~5.000** | **20–40** | **≥ 10 min sostenido** | **Criterio de aceptación de todos los SLO** |
| P3 punto de quiebre | rampa > 2.100 | rampa > 5.000 | 40+ | hasta romper | Punto de quiebre del backplane (D3); margen/headroom |
| P4 caos | ~2.100 | ~5.000 | 20–40 | durante P2 | Caída de instancia/nodo + reconexión; exactly-once |

> Heartbeats /5s → ~200 inserts/s; eventos normales → ~1.000 inserts/s sostenido; **picos hasta ~5.000 inserts/s** en ventana multi-examen (`14`). El escalado ~lineal sostenido→pico es la **Suposición SU-06 a validar en P1→P2**.

## Matriz de decisión por concern (qué métrica promueve qué pieza)

| Concern | Default A4 (hipótesis) | Alternativa SAD | Métrica decisora (al pico P2) | Umbral (`14`) | Veredicto |
|---------|------------------------|-----------------|-------------------------------|---------------|-----------|
| **(a) Cola de trabajos** (asíncrono) | Postgres-cola (`SKIP LOCKED`+pg-boss) | RabbitMQ quorum + Celery | Latencia re-inferencia+firma p99; profundidad de cola estable (no crece sin techo) | **< 30 s** desde subida; cola acotada | Conservar Postgres ✓ si sostiene < 30 s con cola estable al pico; promover RabbitMQ ✗ si la cola crece sin techo o p99 > 30 s |
| **(b) Transporte del panel** (tiempo real) | SSE + backplane (sin sticky) | WebSocket + sticky | Continuidad de suscripción bajo redistribución de instancias; reconexión automática; sin pérdida de suscripción al caer instancia | Sin pérdida de suscripción; reconexión transparente | Conservar SSE ✓ si reparte sin sticky y reconecta solo; promover WS+sticky ✗ solo si SSE no sostiene la redistribución |
| **(c) Backplane de eventos** ⚠️ riesgo #1 (tiempo real) | Postgres `LISTEN/NOTIFY` | Redis Pub/Sub | **p99 de propagación evento→panel** con N=20–40 paneles activos **EN SOSTENIDO AL PICO** | **< 500 ms** | **`LISTEN/NOTIFY` sostiene ✓** si p99 < 500 ms al pico con margen; **se promueve Redis ✗** si p99 ≥ 500 ms o el punto de quiebre cae por debajo del pico requerido |

> **Regla de oro (DD-19)**: la columna "Default A4" gana **por omisión**; la "Alternativa SAD" solo entra si la "Métrica decisora" **cruza el umbral en contra**. La carga de la prueba la lleva quien quiera promover complejidad. Toda promoción se documenta como **evolución condicionada en el ADR**, no como retrabajo.

## Punto de quiebre esperado del backplane (hipótesis a falsar)

`LISTEN/NOTIFY` tiene dos límites estructurales conocidos:
1. **Serialización por conexión**: el `NOTIFY` viaja por la conexión del backend; el fan-out a M instancias no es paralelo a nivel de la cola de notificación de Postgres.
2. **Lock global en commit**: cada `NOTIFY` toma `NotifyQueueLock` al commitear; a alta frecuencia, ese lock serializa los commits y añade latencia de cola.

**Hipótesis de trabajo**: con N=20–40 paneles y ~5.000 eventos/s de fan-out, `LISTEN/NOTIFY` tiene **probabilidad alta de cruzar p99=500 ms** antes que Redis. El barrido P3 debe localizar el evento/s donde p99 cruza 500 ms y compararlo con el pico requerido:
- Si **punto de quiebre > pico requerido con margen** → `LISTEN/NOTIFY` sostiene ✓ (conservar A4; documentar la cota de migración para producción).
- Si **punto de quiebre ≤ pico requerido** → se promueve Redis Pub/Sub ✗ (evolución documentada; Redis sub-50 ms diseñado para fan-out).

Este es el resultado que el change debe producir **explícitamente** y por escrito, con el número del punto de quiebre.

## Risks / Trade-offs

- **[El harness sintético no reproduce el perfil de tráfico real]** → Mitigación: calibrar generadores contra el capacity model del `14` (heartbeats /5s, eventos normales, ráfaga multi-examen, N paneles ≈ 1 proctor/50–100 estudiantes); validar P1 contra el sostenido conocido antes de confiar en P2.
- **[Medir en reposo y dar falso ✓ a `LISTEN/NOTIFY`]** → Mitigación: D2 — el criterio se evalúa SOLO en P2 (sostenido al pico); P0/P1 son sanidad, no aceptación.
- **[Promover Redis/RabbitMQ por una métrica mal aislada]** → Mitigación: D1 — concerns independientes; cada veredicto cita su propia métrica y su propio umbral.
- **[Arrastrar código de PoC a producción]** → Mitigación: D4 — código descartable; C-04…C-15 re-implementan el ganador.
- **[La Suposición de escalado lineal (SU-06) es falsa]** → Mitigación: P1→P2 la mide directamente; si el escalado no es lineal, el veredicto lo documenta y re-dimensiona.
- **Trade-off aceptado**: la PoC retrasa el inicio de C-04 algunas semanas. Es deliberado y barato comparado con construir tres piezas de mensajería sobre una apuesta, o construir una y descubrir en producción que no sostiene el pico.

## Migration Plan

No hay migración de software en producción (no existe sistema). "Despliegue" = ejecución del experimento y registro del veredicto:

1. Montar el harness y la instrumentación (Prometheus/Tempo/Grafana) — instrumentación **antes** de cargar (D5).
2. Validar sanidad con P0 y el escalado sostenido con P1 (valida SU-06).
3. Correr P2 (pico, criterio) para cada concern, opción A (default) y B (alternativa).
4. Correr P3 (punto de quiebre) sobre el backplane (D3) y P4 (caos) para exactly-once.
5. Leer métricas, aplicar la matriz de decisión, registrar **veredicto por concern**.
6. **Criterio de salida del gate**: veredicto por concern documentado (incluyendo el del backplane: sostiene ✓ / se promueve ✗) → desbloquea C-04 con la infraestructura decidida.

**Rollback**: no hay rollback de software. Si la PoC es inconcluyente (instrumentación insuficiente, perfil mal calibrado), se itera el harness y se repite la corrida; ningún change downstream inicia hasta tener veredicto.

## Open Questions

Las que este change debe **cerrar** (no quedan abiertas al archivar):
- **IN-01** — ¿Cola del MVP: Postgres-como-cola o RabbitMQ+Celery? → veredicto por métrica del concern (a).
- **IN-02** — ¿Transporte del panel: SSE+backplane o WebSocket+sticky? → veredicto por métrica del concern (b).
- ¿`LISTEN/NOTIFY` sostiene el fan-out al pico o se promueve Redis? → veredicto explícito del concern (c) con el punto de quiebre.
- ¿La Suposición de escalado ~lineal de inserts (SU-06) se sostiene? → medida en P1→P2.

Las que **quedan fuera** de este change (otros changes):
- Esquema de evento versionado definitivo, validación de firma HMAC de producción → C-10.
- Implementación de producción del ganador (cualquiera sea) → C-04/C-10/C-12/C-15.
- Canal WebSocket del estudiante como diseño (aquí es solo generador de carga) → C-10.
