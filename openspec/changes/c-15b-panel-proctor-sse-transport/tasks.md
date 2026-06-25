# Tasks — C-15b `panel-proctor-sse-transport`

> Tiempo real del panel del proctor, **scoped-out de C-15**. Todo acá depende del
> veredicto de **C-03** (transporte b + backplane c) y de **C-13** (score vía continuous
> aggregates). El Done de cada tarea es un test verde + (donde aplica) métrica contra el SLO.

> **GATE: NO arrancar hasta que C-03 esté en `[x]`** (regla dura de dominio #4: ningún
> agente asume arquitectura de mensajería/transporte antes de C-03). El adaptador concreto
> de cada puerto ES el ganador de C-03. La priorización (§2) depende además de C-13.

## 1. Transporte SSE sin sticky (capability `proctor-sse-transport`) — ⛔ depende de C-03

- [ ] 1.1 Definir `PanelTransportPort` e implementar el adaptador **SSE** (ganador concern b de C-03); Done: test de stream SSE unidireccional
- [ ] 1.2 Definir `EventBackplanePort` e implementar el adaptador del **backplane** (ganador concern c de C-03: `LISTEN/NOTIFY` o Redis); Done: test de publish/subscribe en el backplane
- [ ] 1.3 Cablear el fan-out de C-10 → backplane → push SSE a paneles suscriptos; Done: test de entrega evento→panel
- [ ] 1.4 Reconexión transparente: caída de instancia → panel reconecta a otra sin perder suscripción; Done: test de reconexión sin sticky

## 2. Priorización por score y alertas < 500 ms (capability `proctor-panel-prioritization`) — ⛔ depende de C-03 (§1) + continuous aggregates + score C-13

- [ ] 2.1 Leer sesiones priorizadas por score desde **continuous aggregates** (CQRS-lite, score de C-13); Done: test de orden por score descendente
- [ ] 2.2 Push de **alertas críticas** por el camino de baja latencia (separado del refresco de grilla); Done: test de separación de caminos
- [ ] 2.3 Instrumentar p99 de propagación de alerta crítica; Done: métrica visible (Métrica: alerta p99 < 500 ms en sostenido)
- [ ] 2.4 Refresco de grilla desde el agregado (tolera lag, no sujeto al SLO de 500 ms); Done: test de refresco de grilla

## 3. Acceso — MFA (capability `proctor-contextual-access`)

> El acceso por rol (RBAC) ya se entregó en C-15. "Solo exámenes asignados" (RN-AU-07)
> quedó superseded por decisión del dueño. Queda solo el segundo factor.

- [ ] 3.1 **MFA obligatorio** para el panel (RN-AU-05) — entra cuando el provider JWT propio emita segundo factor (ver C-68). Done: test de denegación sin MFA.

## 4. Cierre

- [ ] 4.1 Test e2e: evento crítico → alerta en panel < 500 ms → proctor actúa (mensaje/cierre); Done: flujo extremo a extremo verde con el SLO respetado (exige el transporte ganador de §1)
