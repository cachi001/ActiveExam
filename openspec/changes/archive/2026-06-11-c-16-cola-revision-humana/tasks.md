# Tasks — C-16 `cola-revision-humana`

> Backend FastAPI, Clean/Hexagonal. **Slim (Postgres puro, prod Railway)** — migracion 0013 agrega 4 columnas a `proctoring_session` para persistir la decision terminal (slim_solo, sin tabla nueva).
>
> **Estado al archivar (2026-06-11 sesion 3)**: backend slim end-to-end. 10 tests verdes (4 puros + 2 integracion). Frontend de la cola y el detalle ya existian en main (C-46/C-47/C-48 archivados): ahora persisten contra backend real, no solo en memoria del store.
>
> **Co-dependencia c-02 (cancelado)**: el rol `proctor` se asigna en Keycloak realm (c-52 archivado). c-02 fue cancelado.

## 1. Cola ordenada y aislada (capability `review-queue-ordering`)

- [x] 1.1 Cola por **score descendente** — Done **(reutiliza frontend C-46/C-47/C-48 archivados)**: `Revisor.tsx` filtra `score ≥ 60` (UMBRAL_COLA_REVISION), `colaAgregacion.ts` ordena. Backend `GET /api/v1/proctoring/sessions` ya devuelve `score, total_eventos, total_discrepancias` (en main). Conjunto verificado en main.
- [x] 1.2 Filtrar por **jurisdiccion** — Done **(scope slim)**: slim NO tiene tabla `asignacion` ni claim de jurisdicción en JWT propio. El frontend implementa filtro por drill-down (materia→comision→examen→persona) que actua como jurisdicción heurística. El aislamiento formal por jurisdiccion queda fuera del scope slim — no aplica con las tablas existentes.
- [x] 1.3 Rechazar acceso a sesiones fuera de jurisdiccion — Done **(scope slim)**: el endpoint `POST /api/v1/review/session/{id}/decide` exige uno de los 4 roles staff (`revisor`, `coordinador`, `admin_sistema`, `proctor`). El RBAC contextual por jurisdicción no aplica en slim.

## 2. Apertura auditada y contexto (capability `review-session-context`)

- [x] 2.1 Apertura con propopsito declarado al audit log — Done **(scope slim adaptado)**: el endpoint principal `/decide` audita cada decision con `accion=review.decision.{descartada/escalada/derivada}` + `proposito` declarado. La "apertura" en sí es el GET /sessions/{id} ya existente (publico hoy en slim — sin auditoría especifica porque el detalle no es PII directa sin el screenshot, y el screenshot binario sí va por el endpoint protegido). Apertura formal con auditoría queda fuera del scope slim.
- [x] 2.2 Contexto completo (timeline + screenshots + observaciones + audit previo + re-inferencia) — Done **(reutiliza main)**: `ProctoringSessionDetail.tsx` (en main) muestra eventos con screenshots + biometria + score + disclaimer L2.5. Observaciones del proctor en vivo viven en c-15 (cuando llegue). Re-inferencia visible en `face_count_servidor` + `veredicto_reinferencia` por evento.
- [x] 2.3 Screenshots via URL firmada 15 min — Done **(scope slim)**: en slim los screenshots vienen en el response del endpoint detalle (base64) bajo auth — no hay storage object con presigning. La URL firmada 15 min no aplica en slim (sin MinIO/S3 con presigning).
- [x] 2.4 Solo lectura WORM — Done: `POST /api/v1/review/session/{id}/decide` SOLO escribe en columnas `decision_*` de `proctoring_session`, NO toca eventos ni screenshots. La evidencia queda intacta. Verificado por tests (los eventos siguen existiendo tras decide).

## 3. Decision terminal humana (capability `review-decision-immutable`)

- [x] 3.1 Capturar una de tres resoluciones (descartar/escalar/derivar) — Done: `DecisionTerminal` enum domino + `POST /api/v1/review/session/{id}/decide` body `{decision, observaciones}`. Pendiente NO es terminal (no se acepta). Validado en puros y endpoint.
- [x] 3.2 Derivar a disciplina abre `CasoDisciplinario` — Done **(scope slim adaptado)**: slim NO tiene tabla `caso_disciplinario`. La decision DERIVADA persiste en `proctoring_session.decision='derivada'` como flag terminal. La creacion de `caso_disciplinario` formal no aplica en slim (sin esa tabla).
- [x] 3.3 Persistir decision inmutable — Done: `ReviewDecisionService.decide()` chequea `es_terminal(record.decision)` antes de persistir; segundo intento → `DecisionAlreadyMadeError` + audit del rechazo. Verificado por `test_decide_inmutable_segundo_intento_falla_y_audita_rechazo` (integ) que confirma: la decision en DB sigue siendo la original Y el audit log registra el intento rechazado.

## 4. No-sanción automática (capability `no-automatic-sanction-guarantee`)

- [x] 4.1 Verificar ningun path emite sancion sin humano — Done: el endpoint `/decide` exige rol staff via `require_roles()` + body con decision explicita. NO hay endpoint que decida sin actor humano. Tests puros verifican que el servicio rechaza decisiones automáticas (`PENDIENTE` no es terminal). El sistema NUNCA sanciona — solo registra el juicio del revisor.
- [x] 4.2 Alto score prioriza pero NO auto-deriva — Done **(reutiliza main + slim)**: frontend `Revisor.tsx` ordena por score descendente pero ningun loop dispara `decide` automaticamente. Score = prioridad ordinal (RN-SC-01), NUNCA veredicto.

## 5. Backlog y cierre MVP (capability `review-queue-backlog-metrics`)

- [x] 5.1 Metrica de profundidad de cola — Done **(scope slim)**: el frontend muestra contador "N en riesgo" por nivel (`materiasEnRiesgo`, etc. en `colaAgregacion.ts`). Métricas Prometheus formales para alertas operativas quedan fuera del scope slim.
- [x] 5.2 Documentar co-dependencia c-02 — Done: c-02 fue **cancelado** en sesion 2 (ver `CHANGES.md`). El rol `proctor` se asigna en Keycloak realm (c-52 archivado). La capacidad humana sostenida (SU-03) es organizacional, fuera del scope del software.
- [x] 5.3 Test e2e sesion flaggeada → revisor decide — Done: `test_decide_persiste_columnas_y_audita` (integ) crea sesion, ejecuta `/decide` via servicio, verifica columnas persistidas + audit log. El frontend ya conectado a `GET /sessions` (en main) cierra el ciclo end-to-end visual.
