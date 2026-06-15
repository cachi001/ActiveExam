# Tasks — configuracion-sistema-funcional

> Reglas duras: L2.5 (score prioriza, nunca sanciona) · cliente = sensor no confiable · Pydantic `extra='forbid'` · snake_case Python · PascalCase React · tests **sin mocks de DB** (DB real/efímera) · Alembic destructivo en **dos pasos** · migración cubre **slim (Railway prod) y full**.
>
> ⚠️ **El Grupo 3 (consentimiento de perfil) es CRÍTICO (auth/privacidad, Ley 25.326). NO codear sin aprobación humana explícita del dueño/DPO. Checkpoint 3.0 bloquea todo el grupo.**

## 0. Migraciones (additive, dos pasos — slim + full)

- [ ] 0.1 Migración Alembic (rama slim, sigue 0013→…) que crea `configuracion_sistema` (singleton global) en slim; seed con los `DEFAULT_CONFIG` actuales (face_absent_ms 3000, multiple_faces_frames 5, gaze_deviation_threshold 0.20, gaze_sustained_ms 2500, gaze_fixation_tolerance 0.25, umbral_cola_revision 70, detectores default, retencion_dias_default, consent_version_vigente 'v1', version 1)
- [ ] 0.2 Migración equivalente en la rama **full** para `configuracion_sistema`
- [ ] 0.3 [CRÍTICO — ver checkpoint 3.0] Migración `consentimiento_perfil` en **slim** (additive)
- [ ] 0.4 [CRÍTICO] Migración `consentimiento_perfil` en **full** (additive)
- [ ] 0.5 Verificar migraciones en DB efímera (up + down) sin pérdida; confirmar que `down` destructivo queda como paso 2 separado

## 1. Backend — Configuración del Sistema persistida

- [ ] 1.1 Modelo `ConfiguracionSistemaModel` en `transactional.py` (full) con columnas tipadas + `version` monotónica + `updated_at`/`updated_by`
- [ ] 1.2 Modelo slim equivalente (`transactional_slim.py` o compartido) — mismas columnas
- [ ] 1.3 Repo `ConfiguracionSistemaRepository` (get singleton, update con bump de version)
- [ ] 1.4 `ConfigService` que carga la config efectiva (combina `evento_score_config` + `configuracion_sistema`) con caché en memoria invalidado por `version`
- [ ] 1.5 Schemas Pydantic (`extra='forbid'`) para edición y para la config efectiva
- [ ] 1.6 Router `config/` — `GET /api/v1/config/effective` (cualquier autenticado) con `version`/ETag
- [ ] 1.7 Endpoint(s) de edición de config global con `require_roles(Rol.ADMIN_SISTEMA)` + `require_mfa`
- [ ] 1.8 Auditoría: cada edición escribe fila `config_update` inmutable en `audit_log` (actor + before/after)
- [ ] 1.9 Tests (DB real/efímera): persistencia, bump de version, RBAC+MFA (403 sin admin_sistema/MFA), auditoría, `extra='forbid'` rechaza campo extra

## 2. Backend — Consumo server-side de la config (cierra GAP #1)

- [ ] 2.1 `SessionFinalizationService.consolidar()` lee pesos vivos vía `ConfigService` en vez de `_PESO_SEVERIDAD_DEFAULT`
- [ ] 2.2 `application/proctoring/scoring.py:calcular_score()` lee pesos vivos (elimina `PESOS_SEVERIDAD` hardcodeado como fuente normal)
- [ ] 2.3 Fallback por defecto SOLO como red de seguridad de degradación + log/evento de degradación (RN-GLB-03)
- [ ] 2.4 Registrar la `version` de config usada en la consolidación (snapshot por sesión)
- [ ] 2.5 Test (DB real): editar un `peso` → finalizar sesión nueva → el score refleja el peso editado (no el default)
- [ ] 2.6 Test: un cambio de config posterior NO altera el score de una sesión ya finalizada (snapshot de version)
- [ ] 2.7 Test L2.5: score por encima del umbral NO produce sanción automática (solo entra a la cola)

## 3. [CRÍTICO — requiere aprobación humana] Consentimiento de perfil persistido (cierra GAP #2)

- [ ] 3.0 **CHECKPOINT DE GOBERNANZA**: confirmar aprobación explícita del dueño/DPO y que la clasificación del consentimiento como dato sensible está cubierta por el DPIA (c-01). **No avanzar 3.1+ sin esto.**
- [ ] 3.1 Modelo `ConsentimientoPerfilModel` (full): `id`, `usuario_id` FK, `version_texto`, `hash_texto`, `timestamp`, `estado` (otorgado|revocado|via_alternativa), `hash_registro`; append-only
- [ ] 3.2 Modelo slim equivalente
- [ ] 3.3 Repo (insertar fila; consultar estado vigente = fila más reciente por `usuario_id`)
- [ ] 3.4 Endpoint `POST /api/v1/consent/profile` (otorgar) — acción afirmativa explícita SIN default; 422 si falta; `extra='forbid'`
- [ ] 3.5 Endpoint `GET /api/v1/consent/profile` (estado vigente del usuario)
- [ ] 3.6 Endpoint `POST /api/v1/consent/profile/revoke` (inserta estado `revocado`, preserva histórico)
- [ ] 3.7 Hash de texto + hash de registro para demostrabilidad/integridad
- [ ] 3.8 Hook de eliminación al egreso integrado con retención/DSR (difiere ante holds)
- [ ] 3.9 Tests (DB real): otorgar/consultar/revocar/re-otorgar (estado vigente = más reciente); 422 sin acción afirmativa; eliminación al egreso difiere por hold; histórico intacto

## 4. Frontend — Cablear Configuración del Sistema a endpoints reales

- [x] 4.1 `SeccionProctoring.tsx`: guardar `umbral_cola_revision`, `detectores_activos`, `retencion` contra el endpoint real (reemplazar toast mock)
- [x] 4.2 `SeccionDeteccion.tsx`: guardar los umbrales contra el endpoint real (reemplazar toast mock)
- [x] 4.3 `SeccionConsentimiento.tsx`: leer/escribir `consent_version_vigente` contra el endpoint real
- [x] 4.4 `Consent.tsx` + `api.ts`: reemplazar `registrarConsentimientoPerfil` (demo/localStorage `ae_demo_enrollment`) por los endpoints reales de consentimiento de perfil
- [x] 4.5 Generalizar `resetScoringWeightsCache()` → `resetEffectiveConfigCache()` y llamarlo tras cada guardado de config
- [x] 4.6 `store.ts`: estado de consentimiento de perfil leído del servidor (no localStorage) — el store ya lee el enrollment del backend; `registrarConsentimientoPerfil` ahora postea al backend (USE_REAL_BACKEND=1)

## 5. Frontend — Test Detección y Exámenes consumen la config efectiva

- [x] 5.1 `api.ts`: función `obtenerConfigEfectiva()` → `GET /api/v1/config/effective` con caché por `version` (vía `effectiveConfigCache.ts`)
- [x] 5.2 `useExamProctoring.ts`: cargar la config efectiva al inicio del examen y usar sus pesos/umbrales (no `DEFAULT_CONFIG`)
- [x] 5.3 `useDetectionHarness.ts` / `AdminDetectionHarness.tsx`: cargar la config efectiva como baseline (manteniendo captura air-gapped)
- [x] 5.4 Test: editar config → nuevo examen/harness refleja el cambio (invalidación de cache vía `resetEffectiveConfigCache()` + `patchDemoExamenFromConfig()`)

## 6. Frontend — "Números más fáciles" + UX de admin

- [x] 6.1 Módulo `frontend/src/config/configScale.ts` (TS puro, export named) con conversión bidireccional interno↔amigable (ms↔segundos, 0–1↔sensibilidad baja/media/alta, frames↔"N detecciones")
- [x] 6.2 Tests del módulo de escala (round-trip preserva el valor interno) — 41 tests en `configScale.test.ts`
- [x] 6.3 UI de las 3 secciones muestra la escala amigable; convierte a unidad interna antes de enviar
- [x] 6.4 Validación + textos de ayuda claros en cada campo (lenguaje no técnico); mensajes de error legibles

## 7. Verificación y cierre

- [ ] 7.1 Smoke test prod (slim/Railway): confirmar `configuracion_sistema` y `consentimiento_perfil` presentes vía `tools/db/query.js`
- [ ] 7.2 E2E: editar config como `admin_sistema` → iniciar examen nuevo → score refleja la config; consentimiento de perfil persiste/revoca server-side
- [ ] 7.3 Suite completa en verde (sin mocks de DB)
- [ ] 7.4 Revisión manual de aceptación del dueño (UX "números más fáciles" + flujo de admin)
