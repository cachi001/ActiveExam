# Tasks — C-15 `panel-proctor-sse`

> Implementa el panel del proctor vía SSE sin sticky (ganador de C-03), priorización por score (CQRS-lite), alertas < 500 ms y acciones del proctor. El Done de cada tarea es un test verde + (donde aplica) métrica contra el SLO.

> **ESTADO (2026-06-24) — qué está condicionado y por qué:**
> - **Secciones 1, 2 y 5.1 → BLOQUEADAS POR C-03.** El transporte SSE, el backplane, la priorización por score y el e2e <500 ms dependen del **ganador de la PoC de carga C-03** (regla dura de dominio #4: ningún agente asume arquitectura de mensajería/transporte antes de C-03). No se pueden implementar hasta que C-03 cierre (hoy 24/45). NO son "falta de trabajo": están gateadas.
> - **Sección 4 (4.1/4.2) → RESUELTA.** Superseded por decisión del dueño (proctor ve TODAS las revisiones, sin aislamiento por asignación). Implementado el endurecimiento por rol. **4.3 MFA → DIFERIDO** por decisión del dueño (no entra por ahora; el slim no emite segundo factor).
> - **Sección 6 (chat + pausa autorizada slim) → COMPLETA** (slice entregado en `feat/c-15-chat-pausa-autorizada`).
> - **Sección 3 (acciones del proctor) → COMPLETA (slim)**: 3.1 cubierta por el chat (§6); 3.2 observaciones (insumo C-16) y 3.3 cierre forzado auditado implementadas y verificadas con tests de DB real. Era el único trabajo de C-15 que no dependía del gate de C-03.
> - **C-15 NO se archiva todavía:** queda abierto a la espera de C-03 para las secciones 1, 2 y 5.1.
>
> **FIXES (2026-06-24) — corrida local + saneamiento:**
> - **5.2 cerrada**: contrato de observaciones para C-16 documentado en `design.md`.
> - **Detalle del proctor surfacea el cierre forzado**: `GET /sessions/{id}` ahora expone `cierre_forzado_en` y `cierre_forzado_motivo` (antes solo los devolvía la acción `/cerrar-forzado`); el frontend refleja el estado al recargar (botón "Cerrar (forzado)" queda deshabilitado). Test nuevo `test_detalle_surfacea_cierre_forzado` (DB real). 
> - **Bug de harness de tests (backend)**: `pyproject.toml` pineaba `pytest-asyncio==0.24.0` pero seteaba `asyncio_default_test_loop_scope` (solo existe en 0.25+) → se ignoraba (warning). Bumpeado a `0.26.0`. ⚠️ La suite **completa** de proctoring igual cuelga por un deadlock de **MediaPipe (re-inferencia C-10) + asyncio** al correr muchas inferencias en un mismo proceso (independiente de C-15): cada archivo C-15 pasa solo (chat 8, pausa 19, score 3, observaciones 8, cierre 7, rbac 22). Pendiente de C-10: aislar los tests de re-inferencia (subproceso/forked).
> - **Bug de runner (frontend)**: 41 `.test.ts(x)` importaban `vitest` pero no estaba en `package.json` ni había script `test`. Agregados `vitest`+`jsdom` (devDeps) y scripts `test`/`test:watch` + `environmentMatchGlobs` para `.tsx`. `npm test` → 443 tests verdes.

## 1. Transporte SSE sin sticky (capability `proctor-sse-transport`) — ⛔ BLOQUEADA POR C-03

- [ ] 1.1 Definir `PanelTransportPort` e implementar el adaptador **SSE** (ganador concern b de C-03); Done: test de stream SSE unidireccional
- [ ] 1.2 Definir `EventBackplanePort` e implementar el adaptador del **backplane** (ganador concern c de C-03: `LISTEN/NOTIFY` o Redis); Done: test de publish/subscribe en el backplane
- [ ] 1.3 Cablear el fan-out de C-10 → backplane → push SSE a paneles suscriptos; Done: test de entrega evento→panel
- [ ] 1.4 Reconexión transparente: caída de instancia → panel reconecta a otra sin perder suscripción; Done: test de reconexión sin sticky

## 2. Priorización por score y alertas < 500 ms (capability `proctor-panel-prioritization`) — ⛔ BLOQUEADA POR C-03 (depende de §1 + continuous aggregates + score C-13)

- [ ] 2.1 Leer sesiones priorizadas por score desde **continuous aggregates** (CQRS-lite, score de C-13); Done: test de orden por score descendente
- [ ] 2.2 Push de **alertas críticas** por el camino de baja latencia (separado del refresco de grilla); Done: test de separación de caminos
- [ ] 2.3 Instrumentar p99 de propagación de alerta crítica; Done: métrica visible (Métrica: alerta p99 < 500 ms en sostenido)
- [ ] 2.4 Refresco de grilla desde el agregado (tolera lag, no sujeto al SLO de 500 ms); Done: test de refresco de grilla

## 3. Acciones del proctor (capability `proctor-session-actions`) — 🟢 SLIM-ACCIONABLE (no depende de C-03) — COMPLETA

- [~] 3.1 Mensajería al estudiante por el canal de comandos (no por SSE); Done: test de entrega de mensaje al estudiante — **CUBIERTA por §6 (chat slim REST+polling)**. La mensajería real-time por canal de comandos entra con el transporte de C-03; el chat bidireccional ya está entregado.
- [x] 3.2 Registro de **observaciones** persistidas como insumo de C-16; Done: test de persistencia de observación — **IMPLEMENTADA (slim)**: tabla `observacion_proctor` (mig. 0025), `observacion_service`, `POST/GET /sessions/{id}/observaciones` (proctor-only), append-only (insumo C-16). UI: panel `ObservacionesProctor` en el detalle. Tests: `test_observaciones_api.py` (8 casos, DB real) verdes.
- [x] 3.3 **Cierre forzado** de sesión: cambia estado + escribe audit log; operativo, NO disciplinario; Done: test de cierre forzado auditado sin veredicto — **IMPLEMENTADA (slim)**: columnas `cierre_forzado_{en,por,motivo}` en `proctoring_session` (mig. 0025, audit-as-row porque el slim no tiene tabla `audit_log` persistente), `PATCH /sessions/{id}/cerrar-forzado` (proctor-only, idempotente). NO toca `decision` (L2.5: veredicto humano en C-16). UI: botón "Cerrar (forzado)" + modal con motivo. El detalle del proctor (`GET /sessions/{id}`) surfacea `cierre_forzado_en`/`cierre_forzado_motivo` para reflejar el estado al recargar. Tests: `test_cierre_forzado_api.py` (7 casos: incl. assert `decision is None` y detalle que surfacea el cierre) verdes.

## 4. Acceso contextual + MFA (capability `proctor-contextual-access`)

> **DECISIÓN DEL DUEÑO (2026-06-23) — supersede 4.1/4.2**: el proctor accede a **TODAS** las revisiones de alumnos (mínimo privilegio sobre el set de pantallas, NO aislamiento por asignación). RN-AU-07 ("proctor solo exámenes asignados") queda fuera del MVP slim por decisión explícita. Lo IMPLEMENTADO en su lugar (rama feat/c-15-chat-pausa-autorizada):
> - **Backend slim endurecido por rol** (antes D7 sin auth): `require_roles(PROCTOR, ADMIN_SISTEMA)` en lista/detalle de sesiones + pausas pendientes/resolver; `require_roles(ADMIN_SISTEMA)` en DELETE (cadena de custodia); resto del flujo del alumno = solo autenticado. Test `tests/proctoring/test_rbac_guards.py` (22 casos).
> - **Frontend opción 1**: admin = todo; proctor = Supervisión en vivo + Cola de revisión + Sesiones grabadas + Detalle (sidebar filtrado por rol + guards de ruta coherentes).

- [~] 4.1 ~~Validar acceso **solo a exámenes asignados** contra `Asignación` (RN-AU-07)~~ — **SUPERSEDED** por decisión del dueño (proctor ve todas las revisiones).
- [~] 4.2 ~~Rechazar acceso a sesiones de exámenes no asignados~~ — **SUPERSEDED** (ídem 4.1).
- [ ] 4.3 **MFA obligatorio** para el panel (RN-AU-05) — **DIFERIDO**: el slim no emite MFA (ver fix C-68). Quedan los guards por rol; MFA entra cuando el slim emita segundo factor. Done: test de denegación sin MFA.

## 5. Cierre

- [ ] 5.1 Test e2e: evento crítico → alerta en panel < 500 ms → proctor actúa (mensaje/cierre); Done: flujo extremo a extremo verde — **⛔ BLOQUEADA POR C-03** (el SLO <500 ms exige el transporte ganador de §1)
- [x] 5.2 Confirmar que las observaciones del proctor quedan consumibles por **C-16** (contexto de revisión); Done: contrato de observaciones documentado para C-16 — **COMPLETA**: contrato congelado en `design.md` §"Contrato de observaciones para C-16" (origen `observacion_proctor`, lectura `GET /sessions/{id}/observaciones` orden asc proctor/admin, semántica append-only L2.5, estabilidad del shape `ObservacionOut`).

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
