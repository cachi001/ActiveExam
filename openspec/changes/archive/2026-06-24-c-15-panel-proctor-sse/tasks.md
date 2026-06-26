# Tasks — C-15 `panel-proctor-sse` (scope SLIM entregado)

> Panel del proctor — **slice slim entregado** (REST + polling): acciones del proctor
> (chat, observaciones, cierre forzado), pausa autorizada con contextualización de score,
> y acceso por rol (RBAC). El Done de cada tarea es un test verde (DB real, sin mocks de DB).

> **ESTADO (2026-06-24) — change PARTIDO y listo para archivar:**
> - El **tiempo real de producción** (transporte SSE §1, priorización por score §2, e2e
>   SLO <500 ms 5.1) y el **MFA del panel** (4.3) se movieron al sucesor
>   **`c-15b-panel-proctor-sse-transport`** (depende de C-03 y C-13). No tiene sentido
>   mantener C-15 abierto esperando C-03: el slim ya cumple su valor.
> - **Sección 4 (4.1/4.2) → SUPERSEDED** por decisión del dueño (proctor ve TODAS las
>   revisiones, RBAC por rol, sin aislamiento por asignación). MFA (4.3) → C-15b.
> - **Sección 3 (acciones del proctor) → COMPLETA (slim)**: 3.1 cubierta por el chat (§6);
>   3.2 observaciones (insumo C-16) y 3.3 cierre forzado auditado, verificadas con tests de DB real.
> - **Sección 6 (chat + pausa autorizada slim) → COMPLETA.**
> - **Todo lo que queda en este change está `[x]` o `[~]`** → se archiva por su scope slim.
>
> **FIXES (2026-06-24):**
> - 5.2 cerrada: contrato de observaciones para C-16 documentado en `design.md`.
> - Detalle del proctor surfacea el cierre forzado (`GET /sessions/{id}` expone
>   `cierre_forzado_en`/`cierre_forzado_motivo`); test `test_detalle_surfacea_cierre_forzado`.
> - Backend: `pytest-asyncio` 0.24→0.26 (respeta `asyncio_default_test_loop_scope`).
> - Frontend: runner de vitest configurado (`vitest`+`jsdom`, scripts `test`/`test:watch`).

## 3. Acciones del proctor (capability `proctor-session-actions`) — 🟢 COMPLETA (slim)

- [~] 3.1 Mensajería al estudiante por el canal de comandos (no por SSE); Done: test de entrega de mensaje al estudiante — **CUBIERTA por §6 (chat slim REST+polling)**. La mensajería real-time por canal de comandos entra con el transporte de C-03 (ver C-15b); el chat bidireccional ya está entregado.
- [x] 3.2 Registro de **observaciones** persistidas como insumo de C-16; Done: test de persistencia de observación — **IMPLEMENTADA (slim)**: tabla `observacion_proctor` (mig. 0025), `observacion_service`, `POST/GET /sessions/{id}/observaciones` (proctor-only), append-only (insumo C-16). UI: panel `ObservacionesProctor` en el detalle. Tests: `test_observaciones_api.py` (8 casos, DB real) verdes.
- [x] 3.3 **Cierre forzado** de sesión: cambia estado + escribe audit log; operativo, NO disciplinario; Done: test de cierre forzado auditado sin veredicto — **IMPLEMENTADA (slim)**: columnas `cierre_forzado_{en,por,motivo}` en `proctoring_session` (mig. 0025, audit-as-row porque el slim no tiene tabla `audit_log` persistente), `PATCH /sessions/{id}/cerrar-forzado` (proctor-only, idempotente). NO toca `decision` (L2.5: veredicto humano en C-16). UI: botón "Cerrar (forzado)" + modal con motivo. El detalle del proctor (`GET /sessions/{id}`) surfacea `cierre_forzado_en`/`cierre_forzado_motivo` para reflejar el estado al recargar. Tests: `test_cierre_forzado_api.py` (7 casos: incl. assert `decision is None` y detalle que surfacea el cierre) verdes.

## 4. Acceso por rol (capability `proctor-contextual-access`) — 🟢 COMPLETA (slim)

> **DECISIÓN DEL DUEÑO (2026-06-23) — supersede 4.1/4.2**: el proctor accede a **TODAS** las
> revisiones (mínimo privilegio sobre el set de pantallas, NO aislamiento por asignación).
> RN-AU-07 queda fuera del MVP slim. El **MFA** (4.3) se movió a **C-15b**.
> Lo IMPLEMENTADO (rama feat/c-15-chat-pausa-autorizada):
> - **Backend endurecido por rol**: `require_roles(PROCTOR, ADMIN_SISTEMA)` en lista/detalle
>   de sesiones + pausas pendientes/resolver; `require_roles(ADMIN_SISTEMA)` en DELETE
>   (cadena de custodia); resto del flujo del alumno = solo autenticado. Test
>   `tests/proctoring/test_rbac_guards.py` (22 casos).
> - **Frontend**: admin = todo; proctor = Supervisión en vivo + Cola de revisión + Sesiones
>   grabadas + Detalle (sidebar filtrado por rol + guards de ruta coherentes).

- [~] 4.1 ~~Validar acceso **solo a exámenes asignados** contra `Asignación` (RN-AU-07)~~ — **SUPERSEDED** por decisión del dueño (proctor ve todas las revisiones).
- [~] 4.2 ~~Rechazar acceso a sesiones de exámenes no asignados~~ — **SUPERSEDED** (ídem 4.1).
- [~] 4.3 **MFA obligatorio** — **MOVIDA a `c-15b-panel-proctor-sse-transport`** (el slim no emite segundo factor; entra con C-68 / cuando el provider emita MFA).

## 5. Cierre

- [~] 5.1 ~~Test e2e: evento crítico → alerta en panel < 500 ms → proctor actúa~~ — **MOVIDA a `c-15b`** (el SLO <500 ms exige el transporte ganador de C-03).
- [x] 5.2 Confirmar que las observaciones del proctor quedan consumibles por **C-16** (contexto de revisión); Done: contrato de observaciones documentado para C-16 — **COMPLETA**: contrato congelado en `design.md` §"Contrato de observaciones para C-16" (origen `observacion_proctor`, lectura `GET /sessions/{id}/observaciones` orden asc proctor/admin, semántica append-only L2.5, estabilidad del shape `ObservacionOut`).

## 6. Chat bidireccional + pausa autorizada (slim, REST + polling) — capabilities `proctor-session-actions` (chat) y `proctor-pausa-autorizada`

> Implementación slim: el slim NO monta el WS de C-10; el transporte es REST con polling.
> Aplica regla dura #6 (evidencia firmada server-side, nunca se borra) y #5 (nunca
> sanciona/exime automático). Done de cada tarea = test backend verde (DB real, sin mock de DB).

### 6.1 Backend — datos + migración
- [x] 6.1.1 Modelos ORM `MensajeChatModel` y `PausaAutorizadaModel`; migración slim aditiva. Done: test de creación de tablas + FK CASCADE
### 6.2 Backend — chat bidireccional
- [x] 6.2.1 `POST /sessions/{id}/chat` persiste mensaje; Done: test de persistencia + validación de autor
- [x] 6.2.2 `GET /sessions/{id}/chat?desde=<iso?>` lista mensajes (polling incremental); Done: test de listado ordenado + filtro desde
### 6.3 Backend — pausa autorizada
- [x] 6.3.1 `POST /sessions/{id}/pausas` crea pausa 'solicitada'; Done: test de solicitud
- [x] 6.3.2 `GET /sessions/{id}/pausas` (poll alumno); `GET /pausas/pendientes` (poll proctor); Done: test de ambos listados
- [x] 6.3.3 `PATCH /pausas/{id}` (aprobar|rechazar) resuelve; aprobar abre ventana (inicio_en); Done: test de aprobar/rechazar (la propia tabla `pausa_autorizada` con proctor_actor + timestamps ES el audit trail persistente)
- [x] 6.3.4 `PATCH /pausas/{id}/finalizar` cierra ventana (fin_en, estado 'finalizada'); Done: test de cierre
### 6.4 Backend — contextualización de score (Opción 1, sabor 1a)
- [x] 6.4.1 Helper puro que excluye del score los eventos en ventana de pausa aprobada; Done: ≥2 tests + edge de borde de ventana
- [x] 6.4.2 `GET /sessions/{id}` marca `en_pausa_autorizada` por evento y excluye del score; Done: test de detalle con badge + score sin los eventos de pausa
### 6.5 Frontend
- [x] 6.5.1 Alumno (`Examen.tsx`): chat + "Solicitar pausa" + timer + "Reanudar"; Done: integra contra api real con fallback mock
- [x] 6.5.2 Proctor (detalle): chat + solicitudes de pausa pendientes + Aprobar/Rechazar; eventos en pausa con badge; Done: integra contra api real
- [x] 6.5.3 Capa API (`api.ts`): métodos reales + fallback mock para chat y pausas; Done: dual-mode coherente
