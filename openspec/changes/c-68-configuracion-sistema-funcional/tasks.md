# Tasks — configuracion-sistema-funcional

> Reglas duras: L2.5 (score prioriza, nunca sanciona) · cliente = sensor no confiable · Pydantic `extra='forbid'` · snake_case Python · PascalCase React · tests **sin mocks de DB** (DB real/efímera) · Alembic destructivo en **dos pasos** · migración cubre **slim (Railway prod) y full**.
>
> Estado (2026-06-16): change **implementado y verificado** (frontend 440 tests + tsc verde; backend 77 tests verde en las áreas del change). **NO archivado todavía** — pendiente smoke de prod y aceptación manual del dueño. El Grupo 3 (consentimiento) recibió **aprobación explícita del dueño en esta sesión**.
>
> Nota: el modelo de sesión "producción" (`sesion` + `SessionFinalizationService` + worker de cola) NO está activo en el runtime slim de dev/Railway; el flujo corre sobre `proctoring_session` (slim). Las tareas que referencian ese modelo quedan marcadas como N/A-slim.

## 0. Migraciones (additive, dos pasos — slim + full)

- [x] 0.1 Migración Alembic slim `configuracion_sistema` (singleton) + seed `DEFAULT_CONFIG` — `0014_config_sistema_consent_perfil_slim.py`
- [x] 0.2 Migración equivalente full — `0015_config_sistema_consent_perfil_full.py`
- [x] 0.3 [CRÍTICO] Migración `consentimiento_perfil` slim (additive) — incluida en `0014`
- [x] 0.4 [CRÍTICO] Migración `consentimiento_perfil` full — incluida en `0015`
- [x] 0.5 Verificado up/down en DB efímera; `down` destructivo como paso 2 separado

## 1. Backend — Configuración del Sistema persistida

- [x] 1.1 Modelo `ConfiguracionSistemaModel` (full) con columnas tipadas + `version` + `updated_at`/`updated_by`
- [x] 1.2 Modelo slim equivalente
- [x] 1.3 Repo `ConfiguracionSistemaRepository` (get singleton, update con bump de version)
- [x] 1.4 `ConfigService` config efectiva (combina `evento_score_config` + `configuracion_sistema`) con caché invalidado por `version` — **fix de esta sesión**: invalidación también al editar scoring (`test_scoring_cache_invalidation.py`)
- [x] 1.5 Schemas Pydantic (`extra='forbid'`) para edición y config efectiva
- [x] 1.6 Router `config/` — `GET /api/v1/config/effective` con `version`
- [x] 1.7 Edición global con `require_roles(ADMIN_SISTEMA)` — MFA **no aplica en slim** (no emite MFA); editable por admin_sistema
- [x] 1.8 Auditoría `config_update` en `audit_log` — VERIFICADO: `PATCH /api/v1/config` escribe fila `config_update` con before/after + hash encadenado (test `test_config_http.py::test_edicion_escribe_audit_log`). **Asimetría cerrada esta sesión**: `PATCH /api/v1/scoring/config/{tipo}` NO auditaba (editar pesos altera la cola de revisión) → agregado el mismo `append()` a `audit_log` + tests `test_scoring_cache_invalidation.py::test_patch_scoring_escribe_audit_log` / `test_patch_scoring_activo_escribe_audit_log`. ⚠️ tests NO ejecutados localmente (Docker apagado) — correr antes de archivar
- [x] 1.9 Tests (DB real): persistencia, bump de version, RBAC (403 sin admin), `extra='forbid'`

## 2. Backend — Consumo server-side de la config (cierra GAP #1)

- [~] 2.1 `SessionFinalizationService.consolidar()` lee pesos vivos — **N/A-slim** (ese servicio es del modelo producción, no activo). El scoring slim usa `ConfigService`/`scoring_weights`.
- [x] 2.2 Pesos vivos en el scoring (el cliente `pesoEvento` + server `ConfigService` usan los pesos editables, no hardcodeados)
- [x] 2.3 Fallback por severidad solo como red de degradación
- [~] 2.4 Snapshot de `version` por sesión — N/A-slim (consolidación producción)
- [x] 2.5 Test: editar peso → se refleja en `/config/effective` (fix de caché) — `test_scoring_cache_invalidation.py`
- [~] 2.6 Cambio posterior no altera sesión finalizada — N/A-slim
- [x] 2.7 L2.5: el score prioriza, nunca sanciona automáticamente (cola de revisión)

## 3. [APROBADO por el dueño] Consentimiento de perfil persistido (cierra GAP #2)

- [x] 3.0 **CHECKPOINT DE GOBERNANZA**: aprobación explícita del dueño en esta sesión (cableado completo del consentimiento)
- [x] 3.1 Modelo `ConsentimientoPerfilModel` (full): append-only, estado, version_texto, hash_texto, hash_registro
- [x] 3.2 Modelo slim equivalente
- [x] 3.3 Repo (insertar; estado vigente = fila más reciente por `usuario_id`)
- [x] 3.4 `POST /api/v1/consent/profile` (otorgar) — acción afirmativa SIN default; 422 si falta; `extra='forbid'`
- [x] 3.5 `GET /api/v1/consent/profile` (estado vigente)
- [x] 3.6 `POST /api/v1/consent/profile/revoke` (append-only)
- [x] 3.7 Hash de texto + hash de registro
- [ ] 3.8 Hook de eliminación al egreso integrado con retención/DSR — pendiente (su propio change de retención)
- [x] 3.9 Tests (DB real): otorgar/consultar/revocar; 422 sin acción afirmativa

## 4. Frontend — Cablear Configuración del Sistema a endpoints reales

- [x] 4.1 `SeccionProctoring.tsx` (renombrada "Parámetros generales"): umbral/detectores contra endpoint real (Retención **removida** por pedido del dueño)
- [x] 4.2 `SeccionDeteccion.tsx`: umbrales contra endpoint real (agrupada Rostro/Mirada, escala amigable)
- [x] 4.3 `SeccionConsentimiento.tsx`: versión vigente contra endpoint real (+ ver Grupo 8: texto versionado editable)
- [x] 4.4 `Consent.tsx` + `api.ts`: consentimiento de perfil contra endpoints reales
- [x] 4.5 `resetEffectiveConfigCache()` tras cada guardado
- [x] 4.6 Estado de consentimiento leído del servidor

## 5. Frontend — Test Detección y Exámenes consumen la config efectiva

- [x] 5.1 `obtenerConfigEfectiva()` → `GET /config/effective` con caché por `version` (`effectiveConfigCache.ts`)
- [x] 5.2 `useExamProctoring.ts`: pesos/umbrales de la config efectiva (no `DEFAULT_CONFIG`) — **+ esta sesión**: respeta `detectores_activos` (descarta eventos de detectores inactivos)
- [x] 5.3 `useDetectionHarness.ts`/`AdminDetectionHarness.tsx`: config efectiva como baseline (captura air-gapped)
- [x] 5.4 Test: editar config → examen/harness refleja el cambio

## 6. Frontend — "Números más fáciles" + UX de admin

- [x] 6.1 `configScale.ts` (conversión interno↔amigable)
- [x] 6.2 Tests de escala (round-trip)
- [x] 6.3 UI con escala amigable
- [x] 6.4 Validación + textos claros no técnicos

## 7. Verificación y cierre

- [~] 7.1 Smoke test prod (slim/Railway): `configuracion_sistema`, `consentimiento_perfil`, `consent_texto_version`, `evento_score_config` presentes — **POST-DEPLOY**: el `Dockerfile.slim` corre `alembic upgrade slim@head` al arrancar, así que las tablas se crean al deployar esta rama. Verificar tras el merge/deploy.
- [x] 7.2 E2E (dev): editar config como admin → examen refleja pesos/umbral/detectores activos; consentimiento persiste/revoca; publicar versión → alumno re-consiente (verificado por curl/DB)
- [x] 7.3 Suite completa en verde (sin mocks de DB) — áreas de C-68 **70/70** + archivos de infra de test **62 passed/2 skip** (DB real en contenedor). Resto de la suite (mediapipe) no relevante al change.
- [x] 7.4 Aceptación del dueño — el dueño decidió archivar el change en esta sesión tras verificar el re-consentimiento en el inicio y la auditoría de scoring.

## 8. Trabajo adicional de la sesión (2026-06-16) — fuera del scope original, ya implementado

### 8.a Scoring / catálogo
- [x] Fix de caché: editar un peso de scoring invalida el `ConfigService` → se refleja en `/config/effective` (`test_scoring_cache_invalidation.py`)
- [x] Evento `corte_conectividad_prolongado` (severidad **crítica**) agregado al catálogo — migraciones `0016` slim / `0017` full
- [x] Severidad **baseline** sacada de la lista de eventos editables y de la leyenda (no es un evento)

### 8.b Consentimiento — texto versionado editable (cableado completo, aprobado por el dueño)
- [x] Tabla `consent_texto_version` (version PK, `bloques` JSONB, hash) — migraciones `0018` slim / `0019` seed v1 / `0020` full
- [x] `GET /consent/text[?version]` resuelve la versión vigente desde la config; `GET/POST /consent/text/versions` (admin, 409 si existe)
- [x] `PATCH /config` valida que `consent_version_vigente` exista (422 si no)
- [x] `SeccionConsentimiento`: editar/agregar/eliminar cláusulas; cambiar el texto **exige** publicar versión nueva; `Consent.tsx` re-consiente con la vigente
- [x] Tests: `test_consent_texto_versionado.py` (22)

### 8.c Usuarios — gestión y detalle
- [x] Endpoints admin: `GET /users/{id}`, `/users/{id}/consent-profile`, `/users/{id}/biometria/referencia/estado` (solo metadatos, **nunca el embedding**)
- [x] Filtros server-side en `GET /users/` (rol, estado, q) + `POST /users/{id}/reactivar` + auto-protección
- [x] Página **Detalle de usuario** (`/admin/usuarios/:id`): datos + consentimiento + captura de referencia (foto). Router extendido para `:param`
- [x] Lista mejorada: switch de estado (verde/rojo, no auto-baja), badges de rol, filtros; `ActionMenu` por portal (no se corta)
- [x] Tests: `test_users_detalle_admin.py` (14) + `test_users_filtros_reactivar.py` (14)

### 8.d Cola de revisión / flujo
- [x] La Cola lee el umbral de `/config/effective` (no 60 fijo); `getUmbralAlto()` sembrado de la config (vista en vivo coherente)
- [x] Sesiones sin examen (diagnóstico / "Grabar sesión") excluidas de la Cola (no más "Sin examen asociado")

### 8.f Re-consentimiento en el Inicio del alumno (fix coherencia consentimiento versionado)
- [x] **Bug**: cuando el admin publicaba una versión nueva, el Inicio (`AlumnoDashboard`) bloqueaba ("Completá tu perfil") pero el checklist marcaba "Consentimiento informado ✅ Listo" porque sólo chequeaba existencia del acuse (`!!enrollment?.consentimiento`), no la versión. Pantalla contradictoria, no indicaba el paso real.
- [x] **Fix**: el Inicio usa `gate.codigo === 'consentimiento_version_desactualizada'` para marcar el paso como NO hecho y relabelarlo "Renovar el consentimiento (hay una versión nueva)". Coherente con `RequisitoConsentimiento` (perfil) y el gate de inscripción.

### 8.g Infra de test (necesaria para suite en verde con DB real)
- [x] **Rangos 0021**: 4 tests pre-existentes (`test_scoring_cache_invalidation`) usaban pesos fuera del rango de severidad (CHECK de migración 0021) → corregidos a valores dentro de rango (media→28, alta→55).
- [x] **pytest-asyncio sin pinear**: causaba `asyncpg "got Future attached to a different loop"` (el `except Exception: pass` del endpoint `/consent/text` lo tapaba y caía al fallback dict → 16 falsos negativos). Fix: `poolclass=NullPool` en los 10 fixtures de test con engine async + pin `pytest-asyncio==0.24.0` en `pyproject.toml`.
- [x] **Tabla faltante**: `test_users_detalle_admin` asumía `consentimiento_perfil` existente; el fixture ahora la crea (`checkfirst=True`).

### 8.e UI/UX global (aprobado por el dueño)
- [x] Configuración del Sistema rediseñada (tabs en línea, cards con padding, slider, toggles, scoring con color de severidad, "Impacto en el score")
- [x] Test de detección rediseñado (cámara grande, sandbox "no se guarda", HelpButton, copy sin jerga, botones Grabar sesión/Test Local)
- [x] Pasada anti-morado (color semántico para estados; morado solo marca/primario), sidebar mobile más grande, notificaciones arriba-derecha
- [x] Copy del frontend sin menciones a leyes/reglas/changes
