# Tasks — C-15 `panel-proctor-sse`

> Implementa el panel del proctor vía SSE sin sticky (ganador de C-03), priorización por score (CQRS-lite), alertas < 500 ms y acciones del proctor. El Done de cada tarea es un test verde + (donde aplica) métrica contra el SLO.

## 1. Transporte SSE sin sticky (capability `proctor-sse-transport`)

- [ ] 1.1 Definir `PanelTransportPort` e implementar el adaptador **SSE** (ganador concern b de C-03); Done: test de stream SSE unidireccional
- [ ] 1.2 Definir `EventBackplanePort` e implementar el adaptador del **backplane** (ganador concern c de C-03: `LISTEN/NOTIFY` o Redis); Done: test de publish/subscribe en el backplane
- [ ] 1.3 Cablear el fan-out de C-10 → backplane → push SSE a paneles suscriptos; Done: test de entrega evento→panel
- [ ] 1.4 Reconexión transparente: caída de instancia → panel reconecta a otra sin perder suscripción; Done: test de reconexión sin sticky

## 2. Priorización por score y alertas < 500 ms (capability `proctor-panel-prioritization`)

- [ ] 2.1 Leer sesiones priorizadas por score desde **continuous aggregates** (CQRS-lite, score de C-13); Done: test de orden por score descendente
- [ ] 2.2 Push de **alertas críticas** por el camino de baja latencia (separado del refresco de grilla); Done: test de separación de caminos
- [ ] 2.3 Instrumentar p99 de propagación de alerta crítica; Done: métrica visible (Métrica: alerta p99 < 500 ms en sostenido)
- [ ] 2.4 Refresco de grilla desde el agregado (tolera lag, no sujeto al SLO de 500 ms); Done: test de refresco de grilla

## 3. Acciones del proctor (capability `proctor-session-actions`)

- [ ] 3.1 Mensajería al estudiante por el canal de comandos (no por SSE); Done: test de entrega de mensaje al estudiante
- [ ] 3.2 Registro de **observaciones** persistidas como insumo de C-16; Done: test de persistencia de observación
- [ ] 3.3 **Cierre forzado** de sesión: cambia estado + escribe audit log; operativo, NO disciplinario; Done: test de cierre forzado auditado sin veredicto

## 4. Acceso contextual + MFA (capability `proctor-contextual-access`)

- [ ] 4.1 Validar acceso **solo a exámenes asignados** contra `Asignación` (RN-AU-07); Done: test de aislamiento por asignación
- [ ] 4.2 Rechazar acceso a sesiones de exámenes no asignados; Done: test de rechazo
- [ ] 4.3 **MFA obligatorio** para el panel (RN-AU-05); Done: test de denegación sin MFA

## 5. Cierre

- [ ] 5.1 Test e2e: evento crítico → alerta en panel < 500 ms → proctor actúa (mensaje/cierre); Done: flujo extremo a extremo verde
- [ ] 5.2 Confirmar que las observaciones del proctor quedan consumibles por **C-16** (contexto de revisión); Done: contrato de observaciones documentado para C-16
