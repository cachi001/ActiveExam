# Design — C-15b `panel-proctor-sse-transport`

> El diseño técnico del panel en tiempo real **ya está escrito** en el design de C-15
> (archivado). Este change lo hereda sin re-decidir nada. Ver
> `openspec/changes/archive/<fecha>-c-15-panel-proctor-sse/design.md`, decisiones:
>
> - **D1** — Transporte SSE sin sticky (ganador concern b de C-03) detrás de
>   `PanelTransportPort`.
> - **D2** — Backplane (ganador concern c de C-03) detrás de `EventBackplanePort`.
> - **D3** — Lecturas del panel desde continuous aggregates (CQRS-lite, score de C-13).
> - **D4** — Alertas críticas vs lecturas agregadas: dos caminos para el SLO < 500 ms.
> - **D6** — Acceso contextual + MFA, sin emitir veredictos.
>
> (D5 — acciones de escritura por canal de comandos — ya se entregó en el slim de C-15.)

## Context

C-15 entregó el panel slim (REST + polling) y se archivó. Lo que falta es el **tiempo
real de producción**, que estaba bloqueado por el veredicto de **C-03** (transporte b +
backplane c) y por **C-13** (score vía continuous aggregates). Este change toma esa
porción tal cual la dejó C-15, sin re-diseñar: implementa los puertos `PanelTransportPort`
y `EventBackplanePort` contra el **ganador de C-03**, y la priorización contra el agregado
de C-13.

## Decisions

Heredadas de C-15 (D1–D4, D6). No se re-deciden aquí. La única regla operativa nueva:

### D7 — No arrancar hasta que C-03 cierre
Ninguna task de este change se implementa antes de que C-03 publique su veredicto por
concern (regla dura de dominio #4). El adaptador concreto de `PanelTransportPort` /
`EventBackplanePort` ES el ganador de C-03; elegirlo antes sería una suposición.

## Open Questions

- ¿`LISTEN/NOTIFY` o Redis para el backplane? → lo decide **C-03** (concern c).
- ¿SSE o WebSocket+sticky para el transporte? → lo decide **C-03** (concern b); hipótesis
  A4 = SSE.
- ¿El ganador sostiene p99 < 500 ms con 20–40 paneles al pico? → lo mide C-03; si no, la
  ruta de evolución (Redis) ya quedó documentada.
