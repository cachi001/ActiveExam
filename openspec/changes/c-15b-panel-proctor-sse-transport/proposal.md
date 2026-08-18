# Proposal — C-15b `panel-proctor-sse-transport`

> **Naturaleza**: feature de producción, governance **ALTO**. Es el **scoped-out de C-15**:
> agrupa lo que C-15 NO pudo entregar porque depende del veredicto de la PoC de carga
> **C-03** (transporte/backplane en tiempo real) y de **C-13** (score vía continuous
> aggregates). C-15 ya se archivó con su scope activeexam entregado (chat/pausa/observaciones/
> cierre/RBAC vía REST+polling). Este change toma la posta del **tiempo real**.

## Why

C-15 entregó el panel del proctor en su versión **activeexam** (REST + polling): chat
bidireccional, pausa autorizada, observaciones, cierre forzado y RBAC por rol. Eso
cubre el valor operativo inmediato y **no dependía de C-03**.

Lo que sí depende de C-03 es el **tiempo real de producción**: el transporte SSE sin
sticky y el backplane de fan-out. No se pueden implementar "a ciegas" porque su
adaptador concreto **es** el ganador de C-03 (concern b = transporte; concern c =
backplane `LISTEN/NOTIFY` vs Redis). Escribirlo antes del veredicto violaría la
**regla dura de dominio #4** (ningún agente asume arquitectura de mensajería/transporte
antes de C-03) y obligaría a reescribir si la PoC elige la otra opción.

La **priorización por score** del panel además depende de los **continuous aggregates**
de C-13 (CQRS-lite), y el **SLO duro de alerta p99 < 500 ms** (`14`) solo se puede
cerrar contra el transporte ganador. Por eso se difiere acá, atado a C-03 + C-13.

El **MFA del panel** (RN-AU-05) se difiere por decisión del dueño: el provider JWT
propio del activeexam aún no emite segundo factor (ver C-68).

## What Changes

Implementa el **tiempo real** del panel del proctor, consumiendo el ganador de C-03:

- **Transporte SSE** (concern b de C-03): canal unidireccional servidor→panel, reconecta
  solo, **sin sticky**, detrás de `PanelTransportPort`.
- **Backplane de fan-out** (concern c de C-03): detrás de `EventBackplanePort` (adaptador
  `LISTEN/NOTIFY` o Redis según C-03), de modo que cualquier instancia sirva cualquier panel.
- **Priorización por score**: sesiones ordenadas por score de riesgo leídas de continuous
  aggregates (CQRS-lite, score de C-13); refresco de grilla tolera lag.
- **Alertas críticas < 500 ms**: push de baja latencia separado del refresco de grilla;
  p99 < 500 ms instrumentado en Prometheus (SLO `14`).
- **Reconexión SSE transparente**: caída de instancia → panel reconecta a otra sin perder
  suscripción.
- **MFA obligatorio** del panel (RN-AU-05).

**Decisiones consumidas (no se re-deciden)**: transporte = ganador concern (b) de C-03;
backplane = ganador concern (c) de C-03; score y orden = continuous aggregate de C-13.

**BREAKING**: ninguno. El activeexam entregado por C-15 sigue funcionando; este change agrega
el camino de tiempo real por encima.

## Capabilities

### New Capabilities

- `proctor-sse-transport`: transporte SSE del panel (unidireccional, reconecta solo, sin
  sticky) alimentado por el backplane ganador de C-03, con reconexión transparente.
- `proctor-panel-prioritization`: presentación de sesiones priorizadas por score (CQRS-lite)
  con alertas críticas en p99 < 500 ms.
- `proctor-contextual-access`: MFA obligatorio para el rol proctor (RN-AU-05). El acceso
  contextual por rol (RBAC) ya se entregó en C-15; "solo exámenes asignados" (RN-AU-07)
  quedó superseded por decisión del dueño.

## Impact

- **Dependencias entrantes (gates)**: **C-03** (ganadores de transporte b y backplane c —
  BLOQUEANTE), **C-13** (score y orden vía continuous aggregate), **C-10** (fan-out por
  backplane, ya implementado), **C-06** (MFA).
- **Habilita**: el panel del proctor en vivo de producción (US-011) contra el SLO duro de
  `14`. El activeexam de C-15 ya cubre el flujo funcional mientras tanto.
- **SLO comprometido**: alerta al panel **p99 < 500 ms** (`14`) — el criterio que C-03 mide.
- **Riesgo principal**: que el backplane ganador no sostenga p99 < 500 ms al pico con 20–40
  paneles. Mitigación: puerto abstracto permite swap a Redis; C-03 deja la cota de migración.
- **Gobernanza**: el panel no sanciona; las acciones de escritura van por el canal de
  comandos, no por SSE. La decisión terminal es humana (C-16).
