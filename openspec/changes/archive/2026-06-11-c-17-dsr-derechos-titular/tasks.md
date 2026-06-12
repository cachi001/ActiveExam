# Tasks — C-17 `dsr-derechos-titular`

> Backend FastAPI, Clean/Hexagonal. **Slim (Postgres puro, prod Railway)** — auth con JWT propio (c-55), no Keycloak. Reutiliza el `HoldVerifier` del dominio retention (c-19 archivado) — patrón hexagonal con Null Object para slim.
>
> **Estado al archivar (2026-06-11 sesion 3)**: implementado slim end-to-end. 10 tests verdes (7 puros + 3 integracion @requires_stack), zero regresion.

## 1. Endpoint y enrutamiento DSR (capability `dsr-rights-endpoint`)

- [x] 1.1 `POST /api/v1/dsr/{type}` por tipo — Done: 4 endpoints en `app/presentation/api/v1/dsr/router.py`: `/access`, `/rectification`, `/erasure`, `/portability`. Schemas con `extra='forbid'`. Auth via `get_current_principal` (JWT propio c-55).
- [x] 1.2 Caso de uso `DsrUseCase`, despacho por tipo — Done: `DsrService` en `app/application/dsr/service.py` con `access()`, `rectification()`, `portability()`, `erasure()`.
- [x] 1.3 `access`: devuelve datos personales — Done: `DsrAccessResponse` value object con campos del usuario. Auditado.
- [x] 1.4 `rectification`: corrige email/nombre/apellido + audit — Done: actualiza atomicamente. Verificado en integ (`test_rectification_actualiza_email_real`).
- [x] 1.5 `portability`: exporta JSON estructurado — Done: `DsrPortabilityResponse` con usuario + `session_ids[]`. JSON natural via FastAPI.
- [x] 1.6 Plazo legal + diferidas pendientes — Done **(scope slim)**: documentado en `nota_legal` del response erasure (Ley 25.326 art. 27 — 10 dias habiles).

## 2. Derecho al olvido y holds (capability `right-to-be-forgotten-with-holds`)

- [x] 2.1 `HoldVerifier` consulta casos abiertos — Done **(reutiliza c-19, scope slim)**: `NullHoldVerifier` de c-19 (siempre NO_HOLD en slim porque no hay `caso_disciplinario`). Si en el futuro se agrega tabla `caso_disciplinario`, se reemplaza por una implementacion SQL sin tocar `DsrService` (hexagonal).
- [x] 2.2 `erasure` SIN holds — Done: borra embedding_referencia + foto_referencia + sesiones sin hold, luego anonimiza usuario (eliminado_en=now, email='anon-XXXX@...', nombre/apellido NULL). Verificado por integ.
- [x] 2.3 `erasure` CON holds: difiere — Done: sesiones con HOLD van a `sessions_deferred[]`. Usuario NO se anonimiza si quedan holds (preserva titular para proceso abierto).
- [x] 2.4 `Anonymizer`: PII → seudonimo irreversible — Done: `SqlUserDsrRepository.anonymize_user()`. id_institucional opaco preservado.
- [x] 2.5 Documentar oposicion a decisiones automatizadas (L2.5) — Done: en docstrings + `nota_legal` del response.

## 3. Trazabilidad (capability `dsr-audit-trail`)

- [x] 3.1 Audit log de cada operacion DSR — Done: `SqlDsrAuditor` reusa `AuditLogSqlRepository`. 4 acciones: `dsr.{access,rectification,erasure,portability}`. Cadena hash automatica.
- [x] 3.2 Audit log sin reexponer PII — Done: `proposito` generico, `evidencia_id` = usuario_id (UUID opaco).
- [x] 3.3 Operacion reconstruible — Done: actor, evidencia_id, accion, proposito + cadena hash criptografica.

## 4. Tests

- [x] 4.1 Test access — `test_access_devuelve_datos_y_audita` (puro) + `test_access_devuelve_usuario_real` (integ).
- [x] 4.2 Test rectification — `test_rectification_actualiza_campos_audita` (puro) + `test_rectification_actualiza_email_real` (integ).
- [x] 4.3 Test erasure sin hold — `test_erasure_sin_hold_borra_todo` (puro) + `test_erasure_borra_biometria_y_anonimiza_y_audita` (integ).
- [x] 4.4 Test erasure con hold difiere — `test_erasure_con_holds_difiere_sesiones` (puro).
- [x] 4.5 Test portability — `test_portability_devuelve_estructura_completa` (puro).
- [x] 4.6 Test trazabilidad — verificacion de filas en audit_log dentro de los tests de integracion.
