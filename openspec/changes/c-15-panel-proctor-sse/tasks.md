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

## 6. Chat bidireccional + pausa autorizada (slim, REST + polling) — capabilities `proctor-session-actions` (chat) y `proctor-pausa-autorizada`

> Implementación slim: el slim NO monta el WS de C-10; el transporte es REST con polling (consistente con el panel del proctor, que ya pollea cada 4s). Aplica regla dura #6 (evidencia firmada server-side, nunca se borra) y #5 (nunca sanciona/exime automático). Done de cada tarea = test backend verde (DB real/efímera, sin mock de DB).

### 6.1 Backend — datos + migración
- [x] 6.1.1 Modelos ORM `MensajeChatModel` (session_id, autor 'alumno'|'proctor', actor?, texto, creado_en) y `PausaAutorizadaModel` (session_id, motivo, estado, solicitada_en, resuelta_en?, proctor_actor?, inicio_en?, fin_en?); migración slim aditiva. Done: test de creación de tablas + FK CASCADE
### 6.2 Backend — chat bidireccional
- [x] 6.2.1 `POST /sessions/{id}/chat` (body {autor, texto}) persiste mensaje; Done: test de persistencia + validación de autor
- [x] 6.2.2 `GET /sessions/{id}/chat?desde=<iso?>` lista mensajes (polling incremental); Done: test de listado ordenado + filtro desde
### 6.3 Backend — pausa autorizada
- [x] 6.3.1 `POST /sessions/{id}/pausas` (body {motivo}) crea pausa 'solicitada'; Done: test de solicitud
- [x] 6.3.2 `GET /sessions/{id}/pausas` lista pausas de la sesión (poll del alumno); `GET /pausas/pendientes` lista solicitadas (poll del proctor); Done: test de ambos listados
- [x] 6.3.3 `PATCH /pausas/{id}` (body {accion 'aprobar'|'rechazar', proctor_actor?}) resuelve + escribe audit_log; aprobar abre ventana (inicio_en); Done: test de aprobar/rechazar + entrada audit (NOTA: en el slim NO hay middleware de audit_log por-request cableado — la tabla `audit_log` (mig. 0012) solo la escriben servicios puntuales; la propia tabla `pausa_autorizada` con proctor_actor + timestamps ES el audit trail persistente. Documentado en chat_pausa_service.py)
- [x] 6.3.4 `PATCH /pausas/{id}/finalizar` cierra ventana (fin_en, estado 'finalizada'); Done: test de cierre
### 6.4 Backend — contextualización de score (Opción 1, sabor 1a)
- [x] 6.4.1 Helper puro que dada la lista de eventos y las ventanas de pausa aprobada devuelve los ids de eventos en pausa; `calcular_score` excluye esos eventos; Done: ≥2 tests (con y sin pausa) + edge de borde de ventana
- [x] 6.4.2 `GET /sessions/{id}` (detalle del proctor) marca `en_pausa_autorizada` por evento y excluye del score; Done: test de detalle con badge + score sin los eventos de pausa
### 6.5 Frontend
- [x] 6.5.1 Alumno (`Examen.tsx`): caja de chat (enviar + poll recibir) + botón "Solicitar pausa" con motivo + timer de pausa aprobada + "Reanudar"; Done: integra contra api real con fallback mock
- [x] 6.5.2 Proctor (`Proctor.tsx` / detalle): caja de chat + notificación de solicitudes de pausa pendientes + botones Aprobar/Rechazar; eventos en pausa con badge "pausa autorizada"; Done: integra contra api real
- [x] 6.5.3 Capa API (`api.ts`): métodos reales + fallback mock para chat y pausas; Done: dual-mode coherente con el resto
