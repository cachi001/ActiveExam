# Proposal — C-15 `panel-proctor-sse`

> **Naturaleza del change**: feature de producción, governance **ALTO**. Implementa el **panel del proctor en vivo** (US-011, FR-11). **Usa el ganador de transporte de C-03** (hipótesis A4: SSE + backplane, sin sticky — DD-16). **Depende de C-10** (eventos + backplane). Cierra contra el SLO duro de **alertas al panel < 500 ms** (`14`).

## Why

El proctor en vivo (Martín, `03`) es un recurso humano escaso: ~1 proctor cada 50–100 estudiantes. No puede mirar todas las sesiones. El panel existe para que **atienda solo lo que requiere atención** (`03` §Proctor): sesiones priorizadas por score de riesgo y alertas críticas que llegan **a tiempo de actuar**.

El SLO es duro y medible: **propagación de alerta al panel p99 < 500 ms** (`14`). Una alerta de "múltiples rostros" o "posible cambio de identidad" que llega tarde es inútil: el momento de intervención ya pasó. Ese SLO es exactamente el criterio que **C-03 midió** para decidir el transporte y el backplane (concern b y c). Este change **consume el ganador**, no lo re-decide.

El discovery (DD-16) propone para el panel **SSE** (unidireccional, reconecta solo) en vez de WebSocket+sticky: el panel solo recibe, no necesita un canal bidireccional, y SSE elimina la dependencia de **sticky sessions** que concentra conexiones y acopla el escalado. El backplane (ganador del concern c de C-03: `LISTEN/NOTIFY` por hipótesis, o Redis Pub/Sub si C-03 lo promovió) distribuye los eventos entre instancias para que **cualquier** instancia pueda servir a **cualquier** panel sin sticky. Las lecturas del panel salen de **continuous aggregates** (CQRS-lite, `08`), no de recorrer eventos crudos.

## What Changes

Implementa el panel del proctor con transporte SSE alimentado por el backplane (Flujo 3 §fan-out, US-011):

- **Transporte SSE** (ganador del concern b de C-03): canal **unidireccional** servidor→panel, que **reconecta solo**, **sin sticky sessions** (DD-16). Alimentado por el **backplane** (ganador del concern c de C-03).
- **Priorización por score de riesgo**: las sesiones se presentan ordenadas por score, leyendo de **continuous aggregates** (CQRS-lite, `08` §Patrones) — no se recorre la hypertable cruda.
- **Alertas críticas < 500 ms**: la propagación evento crítico → panel cumple **p99 < 500 ms** (SLO `14`), medido en sostenido.
- **Acciones del proctor**: mensajería al estudiante, registro de **observaciones**, **cierre forzado** de sesión (las acciones de escritura van por el canal de comandos, no por el SSE).
- **Permisos contextuales + MFA**: el proctor ve **solo sus exámenes asignados** (RN-AU-07); **MFA obligatorio** (RN-AU-05).
- **Reconexión SSE transparente**: ante caída de instancia, el panel reconecta a **otra** instancia sin perder la suscripción (gracias a backplane sin sticky).

**Decisiones consumidas (no se re-deciden aquí)**:
- **Transporte del panel** = ganador del **concern (b)** de C-03 (hipótesis SSE+backplane).
- **Backplane de eventos** = ganador del **concern (c)** de C-03 (hipótesis `LISTEN/NOTIFY`; Redis Pub/Sub si C-03 lo promovió).
- El score y su orden vienen del continuous aggregate de C-13; la autenticación/RBAC contextual y MFA de C-06.

**BREAKING**: ninguno. Habilita **C-16** (cola de revisión): las observaciones del proctor registradas aquí forman parte del contexto completo que el revisor consume.

## Capabilities

> Cada SHALL se prueba con un test (priorización por score, latencia de alerta < 500 ms, aislamiento por asignación, cierre forzado, reconexión SSE).

### New Capabilities

- `proctor-sse-transport`: el transporte SSE del panel (unidireccional, reconecta solo, sin sticky) alimentado por el backplane ganador de C-03, con reconexión transparente ante caída de instancia.
- `proctor-panel-prioritization`: la presentación de sesiones priorizadas por score de riesgo, leídas de continuous aggregates (CQRS-lite), con alertas críticas propagadas en p99 < 500 ms.
- `proctor-session-actions`: las acciones del proctor sobre sesiones asignadas — mensajería al estudiante, registro de observaciones y cierre forzado de sesión.
- `proctor-contextual-access`: el control de acceso contextual (solo exámenes asignados) con MFA obligatorio para el rol proctor.

### Modified Capabilities

<!-- Ninguna spec de dominio previa en openspec/specs/. El transporte/backplane (C-03), el score (C-13), la auth/RBAC (C-06) y el canal de eventos (C-10) son dependencias de implementación, no specs a modificar aquí. -->

(Ninguna — este change agrega capacidades nuevas; no modifica requisitos ya especificados en `openspec/specs/`.)

## Impact

- **Habilita**: C-16 (`cola-revision-humana`) — las **observaciones del proctor** registradas aquí son parte del contexto completo que el revisor consume; cierra el ciclo MVP.
- **Dependencias entrantes**: `C-10` (canal de eventos + fan-out por backplane), y transitivamente `C-03` (ganadores de transporte b y backplane c), `C-13` (score y su orden vía continuous aggregate), `C-06` (RBAC contextual + MFA).
- **Decisiones que consume** (de C-03): transporte del panel = ganador concern (b); backplane = ganador concern (c). **Implementado contra puertos abstractos** para enchufar el adaptador del ganador (SSE/WS, `LISTEN/NOTIFY`/Redis).
- **Actores/sistemas afectados**: proctor en vivo (Martín — opera el panel), estudiante (recibe mensajes/cierre forzado), backplane, continuous aggregates de TimescaleDB.
- **SLO comprometido**: alertas al panel **p99 < 500 ms** (`14`) — el criterio que C-03 usó para decidir el backplane. Si el ganador no sostiene el SLO al pico, C-03 ya dejó documentada la ruta de evolución (Redis Pub/Sub).
- **Garantía de gobernanza**: el panel **no sanciona**; el cierre forzado y las observaciones son acciones operativas del proctor, no veredictos disciplinarios (la decisión terminal es de C-16, humana).
- **Riesgo principal**: que el backplane ganador no sostenga p99 < 500 ms con 20–40 paneles activos al pico (riesgo de tiempo real #1 de C-03). Mitigación: el puerto abstracto permite swap a Redis; C-03 dejó la cota de migración.
