# Tasks — C-15b `panel-proctor-sse-transport`

> Tiempo real del panel del proctor, **scoped-out de C-15**. Todo acá depende del
> veredicto de **C-03** (transporte b + backplane c) y de **C-13** (score vía continuous
> aggregates). El Done de cada tarea es un test verde + (donde aplica) métrica contra el SLO.

> **GATE: NO arrancar hasta que C-03 esté en `[x]`** (regla dura de dominio #4: ningún
> agente asume arquitectura de mensajería/transporte antes de C-03). El adaptador concreto
> de cada puerto ES el ganador de C-03. La priorización (§2) depende además de C-13.

## 0. Contexto heredado de c-78 (§16.6) — leer antes de arrancar

> Esta tarea vivía en c-78 como recordatorio y lo mantenía abierto por algo que no le
> pertenecía. El análisis hecho con el dueño el 26/8/2026 se conserva acá, que es donde
> corresponde. **No son tareas nuevas: es contexto para no volver a discutirlo desde cero.**

- **Qué mejora SSE y qué no.** NO hace que el alumno rinda mejor: contestar, autoguardar, la
  cámara y la detección no pasan por el polling. Lo que mejora es la latencia de la pausa
  (~4 s → instantáneo), la supervisión del tutor y el techo de req/s.
- **Por qué se difirió.** Con la cadencia adaptativa del poller (c-78 §16.12) ya se sale de
  la saturación, así que el aporte marginal para 100 alumnos era chico frente al riesgo de
  cambiar el transporte del examen en vivo a días de la fecha.
- **SSE y no WebSocket.** El tráfico es de UNA dirección (el servidor avisa; lo que manda el
  alumno son POST normales que ya andan) y `EventSource` **se reconecta solo** por
  especificación del navegador. Un WebSocket caído en silencio deja al alumno sin
  aprobaciones de pausa y nadie se entera.
- **El bloqueo de la regla dura #4 casi no aplica hoy.** Lo que C-03 tenía que decidir era el
  *backplane* de fan-out entre instancias, y producción corre **un solo proceso** de uvicorn:
  no hay nada que compartir, un pub/sub en memoria alcanza. Verificar contra
  `Dockerfile.activeexam` antes de asumirlo — si algún día se levanta con `--workers`, el
  backplane vuelve a hacer falta y §1.2 recupera su sentido original.

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
