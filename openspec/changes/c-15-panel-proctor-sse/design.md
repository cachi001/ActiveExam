# Design — C-15 `panel-proctor-sse`

> Design técnico de producción del **panel del proctor en vivo** (US-011, Flujo 3 §fan-out). Transporte SSE sin sticky alimentado por backplane (ganadores de C-03), priorización por score vía CQRS-lite, SLO de alerta < 500 ms. Implementado contra puertos abstractos para enchufar el ganador de C-03.

## Context

El proctor en vivo (Martín, `03`) supervisa ~50–100 estudiantes por panel y debe **atender solo lo que requiere atención**. El valor del panel depende de dos cosas: que las sesiones se presenten **priorizadas por riesgo** y que las **alertas críticas lleguen a tiempo de actuar**.

**SLO duro** (`14`): propagación de alerta al panel **p99 < 500 ms**. Este es el mismo SLO que **C-03 midió** para decidir el transporte (concern b) y el backplane (concern c). C-03 es el gate: este change **consume su veredicto**, no re-decide.

**Constraints** (de la KB):
- **DD-16**: el panel usa **SSE** (unidireccional, reconecta solo), no WebSocket+sticky; el **backplane** distribuye eventos entre instancias para eliminar la dependencia de **sticky sessions**.
- **DD-08** (SAD, revisado por A4): el fan-out híbrido y sticky del SAD se revisa a favor de SSE+backplane; la pieza Redis del SAD solo entra si C-03 la promovió.
- **`08` §Patrones (CQRS-lite)**: las lecturas del panel salen de **continuous aggregates** materializados de TimescaleDB, no de recorrer la hypertable.
- **RN-AU-07**: permisos **contextuales** — el proctor ve solo exámenes asignados.
- **RN-AU-05**: **MFA obligatorio** para roles con acceso a evidencia/administración (incluido proctor).
- **RN-EV-04**: "múltiples rostros" → alerta al proctor en **< 500 ms**; "posible cambio de identidad" → atención inmediata.

**Decisiones heredadas (no se re-deciden)**:
- **Transporte del panel** = ganador del **concern (b)** de C-03 (hipótesis A4: SSE+backplane sin sticky; alternativa SAD: WebSocket+sticky).
- **Backplane** = ganador del **concern (c)** de C-03 (hipótesis A4: Postgres `LISTEN/NOTIFY`; alternativa SAD: Redis Pub/Sub, si C-03 lo promovió por no sostener p99<500ms al pico).
- El score y su orden de C-13; auth/RBAC contextual y MFA de C-06; canal de eventos de C-10.

**Stakeholders**: proctor (opera el panel), estudiante (recibe mensajes/cierre), coordinador (asigna proctors), revisor downstream (consume las observaciones vía C-16).

## Goals / Non-Goals

**Goals:**
- Servir el panel por **SSE sin sticky** (ganador de C-03), con reconexión transparente ante caída de instancia.
- Priorizar sesiones por **score de riesgo** leyendo de continuous aggregates (CQRS-lite).
- Cumplir el SLO de **alerta crítica p99 < 500 ms** (medido en sostenido).
- Permitir las acciones del proctor: mensajería, observaciones, **cierre forzado**.
- Aplicar acceso **contextual** (solo exámenes asignados) + **MFA**.

**Non-Goals:**
- NO re-decidir el transporte ni el backplane (lo hizo C-03; aquí se consumen detrás de puertos).
- NO implementar el canal **WebSocket del estudiante** ni la ingesta de eventos (eso es C-10; aquí se **consume** el fan-out).
- NO calcular el score (eso es C-13; aquí se **lee** del continuous aggregate).
- NO implementar la cola de revisión asíncrona ni la decisión terminal (eso es C-16; aquí se registran observaciones que C-16 consume).
- NO emitir veredictos/sanciones: el cierre forzado y las observaciones son operativos, no disciplinarios.

## Decisions

### D1 — Transporte SSE sin sticky (ganador del concern b de C-03), detrás de un puerto abstracto
**Decisión**: el panel se sirve por **SSE** (unidireccional, reconecta solo) detrás de un puerto `PanelTransportPort`; el adaptador concreto es el ganador del concern (b) de C-03 (SSE+backplane por hipótesis; WS+sticky si C-03 lo promovió).
**Por qué**: DD-16 — el panel solo recibe; SSE es más simple que WS y reconecta solo. Sin sticky, cualquier instancia sirve a cualquier panel. El puerto deja la decisión de C-03 enchufable sin tocar el dominio.
**Alternativa considerada**: WebSocket+sticky directo → concentra conexiones, acopla el escalado (DD-16); además fijaría una decisión que C-03 debe haber tomado por métrica.

### D2 — Backplane (ganador del concern c de C-03) detrás de un puerto abstracto
**Decisión**: el fan-out evento→panel pasa por un **backplane** detrás de `EventBackplanePort`; el adaptador es el ganador del concern (c) de C-03 (Postgres `LISTEN/NOTIFY` por hipótesis; Redis Pub/Sub si C-03 lo promovió por p99).
**Por qué**: el backplane es lo que permite SSE sin sticky (cualquier instancia recibe todos los eventos y los reenvía a sus paneles). C-03 midió si `LISTEN/NOTIFY` sostiene p99<500ms al pico; este change enchufa el ganador.
**Alternativa considerada**: fijar Redis o `LISTEN/NOTIFY` aquí → usurpa la decisión medida de C-03.

### D3 — Lecturas del panel desde continuous aggregates (CQRS-lite)
**Decisión**: la lista de sesiones priorizadas y los estados agregados se leen de **continuous aggregates** materializados de TimescaleDB (score por sesión, sesiones activas por examen), no de la hypertable cruda.
**Por qué**: `08` §Patrones (CQRS-lite) — recorrer millones de eventos para pintar el panel no escala; el agregado materializado reduce la latencia de lectura en órdenes de magnitud.
**Alternativa considerada**: query directa a la hypertable por cada refresh del panel → latencia inaceptable bajo carga.

### D4 — Alertas críticas vs lecturas agregadas: dos caminos distintos para el SLO < 500 ms
**Decisión**: las **alertas críticas** (múltiples rostros, posible cambio de identidad) viajan por el **push del backplane → SSE** (camino de baja latencia, sujeto al SLO < 500 ms); la **lista priorizada** se refresca desde los agregados (no sujeta al SLO de 500 ms, tolera el lag del aggregate).
**Por qué**: el SLO de 500 ms aplica a la **alerta accionable**, no al refresco de la grilla. Separarlos permite cumplir el SLO sin recalcular agregados en el path caliente.
**Alternativa considerada**: pintar todo desde el push en tiempo real → satura el backplane con datos no urgentes y arriesga el SLO de las alertas reales.

### D5 — Acciones de escritura por canal de comandos, no por SSE
**Decisión**: mensajería al estudiante, observaciones y **cierre forzado** son **escrituras** que van por endpoints/comando (REST o WS del estudiante para el push al alumno), NO por el SSE (que es unidireccional servidor→panel).
**Por qué**: DD-16 — SSE es unidireccional por diseño; mezclar escrituras rompería el modelo. El cierre forzado modifica el estado de la sesión y debe auditarse.
**Alternativa considerada**: forzar bidireccionalidad sobre SSE → desnaturaliza el transporte; volvería a WS, que C-03 ya evaluó.

### D6 — Acceso contextual + MFA, sin emitir veredictos
**Decisión**: el proctor solo accede a sesiones de **exámenes asignados** (RN-AU-07, validado contra la `Asignación` de C-07), con **MFA obligatorio** (RN-AU-05); las acciones del proctor son **operativas**, nunca disciplinarias.
**Por qué**: aislamiento por asignación es un requisito de seguridad (un proctor no debe ver exámenes ajenos); MFA protege el acceso a datos sensibles. El cierre forzado es operativo (cortar una sesión en curso), no un veredicto (eso es C-16).
**Alternativa considerada**: permisos globales → viola RN-AU-07; acceso sin MFA → viola RN-AU-05.

## Arquitectura del panel

```
                    CONTINUOUS AGGREGATES (TimescaleDB)        ← de C-13
                    score por sesión · sesiones activas/examen
                              │  lectura CQRS-lite [D3]
                              ▼
EVENTOS (C-10) ──► BACKPLANE ──────────────────────► INSTANCIA FastAPI ──SSE──► PANEL (proctor)
  fan-out         [EventBackplanePort, ganador C-03] │  (cualquiera, sin sticky)   unidireccional,
                  LISTEN/NOTIFY | Redis  [D2]         │  [PanelTransportPort,        reconecta solo [D1]
                                                      │   ganador C-03]
   alerta crítica ─push─► ⏱ p99 < 500 ms [D4] ────────┘
        (múltiples rostros, cambio de identidad)

   ACCIONES del proctor (escritura, NO por SSE) [D5]:
     ├─ mensaje al estudiante ──► (canal del estudiante, C-10)
     ├─ observación ───────────► persiste (insumo de C-16)
     └─ cierre forzado ────────► cambia estado de Sesión + audit log

   ACCESO: solo exámenes asignados (RN-AU-07) + MFA (RN-AU-05) [D6]
   reconexión: caída de instancia → reconecta a OTRA instancia, sin perder suscripción [D1+D2]
```

## Risks / Trade-offs

- **[El backplane ganador no sostiene p99 < 500 ms con 20–40 paneles al pico]** (riesgo de tiempo real #1 de C-03) → Mitigación: `EventBackplanePort` permite swap a Redis sin tocar el dominio; C-03 dejó la cota de migración documentada.
- **[SSE no reconecta limpio ante caída de instancia → panel ciego]** → Mitigación: backplane sin sticky (D2) hace que cualquier instancia sirva al panel; test de reconexión transparente; el panel re-suscribe con su contexto de asignación.
- **[Lag del continuous aggregate desactualiza la grilla]** → Trade-off **aceptado** (D4): la grilla tolera el lag (al minuto); las **alertas accionables** van por el push de baja latencia, no por el aggregate.
- **[Confundir cierre forzado con sanción]** → Mitigación: D6 — el cierre forzado es operativo y auditado, no disciplinario; la decisión terminal es de C-16 (humana).
- **[Proctor ve exámenes no asignados]** → Mitigación: D6 — validación contextual contra `Asignación` en cada acceso; test de aislamiento.

## Migration Plan

1. Implementar `PanelTransportPort` + adaptador SSE (ganador concern b de C-03) y `EventBackplanePort` + adaptador del backplane (ganador concern c).
2. Cablear el fan-out de C-10 al backplane → push SSE a los paneles suscriptos a sus asignaciones.
3. Implementar la lectura de sesiones priorizadas desde continuous aggregates (CQRS-lite, score de C-13).
4. Implementar el push de **alertas críticas** con instrumentación de p99 (SLO < 500 ms).
5. Implementar acciones del proctor: mensajería, observaciones (insumo de C-16), cierre forzado (audita).
6. Aplicar acceso contextual (RN-AU-07) + MFA (RN-AU-05).
7. Instrumentar p99 de propagación de alerta y la reconexión SSE.

**Rollback**: feature aislada tras puertos; si el backplane ganador falla el SLO, se swapea el adaptador (Redis) sin reescribir el panel.

## Open Questions

Cerradas por este change:
- ¿Qué transporte/backplane usa el panel? → los ganadores de C-03, vía puertos (D1, D2).
- ¿Cómo se cumple el SLO < 500 ms sin saturar con datos no urgentes? → separar push de alerta y refresco de grilla (D4).

Fuera de alcance (otros changes):
- Decisión del transporte/backplane por métrica → **C-03** (ya tomada).
- Canal WS del estudiante e ingesta de eventos → **C-10**.
- Cálculo del score → **C-13**.
- Cola de revisión asíncrona + decisión terminal + audit de apertura → **C-16**.
