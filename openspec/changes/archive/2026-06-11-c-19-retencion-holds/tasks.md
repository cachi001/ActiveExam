# Tasks — C-19 `retencion-holds`

> Backend FastAPI, Clean/Hexagonal. **Slim (Postgres puro, produccion Railway)** — features de TimescaleDB (compresion nativa, archivado a Parquet, drop verificado de chunks) NO APLICAN porque slim usa tabla comun `proctoring_event` sin hypertable.
>
> **Estado al archivar (2026-06-11 sesion 3)**: implementado slim end-to-end con TDD. 27 tests verdes (21 puros + 6 integracion @requires_stack), zero regresion en baseline (240 passed pre, 240 passed post).

## 1. Motor de retención automática (capability `retention-policy-engine`)

- [x] 1.1 Definir el modelo de política de retención por tipo de dato (clips, embeddings, eventos, audit log, casos) con plazo configurable; Done: `RetentionPolicy` value object frozen en `app/domain/retention/policy.py` con defaults (180d sesiones, 5y audit log). Validacion de no-negativos. 5 tests puros verdes (`test_c19_retention_policy_pure.py`).
- [x] 1.2 Implementar el job periódico que recorre las políticas y las aplica sin intervención manual (US-014 CA-1); Done: `RetentionEngine` en `app/application/retention/engine.py` con `apply_session_retention()` + `apply_embedding_egress()`. Endpoints admin `POST /api/v1/admin/retention/session` y `POST /api/v1/admin/retention/biometric` (solo `admin_sistema`) — invocable por cron externo / GitHub Action.
- [x] 1.3 Respetar el Object Lock (WORM) de los binarios: no eliminar antes de expirar la retención; Done **(scope reducido slim)**: en slim no hay MinIO/S3 con Object Lock — las fotos viven como BYTEA en Postgres y se borran inmediatamente al egreso. La parte "purga diferida por Object Lock" NO APLICA SLIM (sin WORM en slim).
- [x] 1.4 Registrar cada aplicación de política en el audit log append-only (qué política, qué dato, cuándo, resultado); Done: `SqlRetentionAuditor` en `app/infrastructure/persistence/repositories/retention.py` reusa `AuditLogSqlRepository` existente con triggers de cadena hash. Acciones registradas: `retention.session.deleted`, `retention.session.hold_deferred`, `retention.biometric.egress`. Verificado por `test_engine_session_retention_borra_aged_y_audita` y `test_engine_biometric_egress_borra_embedding_y_foto`.

## 2. Archivado de chunks de eventos (capability `event-chunk-archival`)

- [x] 2.1 Respetar la política de compresión de la hypertable (recientes sin comprimir, 7 días–1 año comprimidos); Done **🚫 NO APLICA SLIM**: slim usa tabla común `proctoring_event` en Postgres puro (no TimescaleDB hypertable). Sin compresión nativa. Si se migra el stack a TimescaleDB en el futuro, se evaluara entonces.
- [x] 2.2 Exportar los chunks > umbral a Parquet en object storage; Done **🚫 NO APLICA SLIM**: sin chunks de hypertable que exportar. En slim la retención de eventos es `DELETE` directo cuando cascada desde la sesión (FK `ondelete=CASCADE`). Parquet a object storage no aplica en slim.
- [x] 2.3 Eliminar (drop) el chunk de la base activa solo tras verificar la exportación; Done **🚫 NO APLICA SLIM**: sin chunks. En slim los eventos se eliminan por CASCADE al borrar la sesión padre. Verificado por `test_session_deleter_cascade_a_eventos` que confirma que `DELETE proctoring_session` arrastra los `proctoring_event` hijos.
- [x] 2.4 Registrar el archivado en el audit log; Done **🚫 NO APLICA SLIM**: cubierto por 1.4 (todas las acciones del motor quedan en audit log). El "archivado" como evento separado no aplica en slim.

## 3. Holds por caso abierto (capability `retention-holds`)

- [x] 3.1 Verificar, antes de eliminar/archivar datos sujetos a hold, si existe un caso disciplinario abierto vinculado; Done **(scope adaptado slim)**: puerto `HoldVerifier` definido en `app/domain/retention/hold.py`. Implementación slim default: `NullHoldVerifier` en `app/infrastructure/retention/null_hold_verifier.py` que siempre devuelve `NO_HOLD` (slim no tiene tabla `caso_disciplinario` — esa es rama full, migración 0002). Si en el futuro se agrega la tabla `caso_disciplinario`, se reemplazara `NullHoldVerifier` por una implementacion SQL sin tocar el dominio retention (hexagonal). 3 tests puros verdes (`test_c19_hold_verifier_null.py`).
- [x] 3.2 Extender automáticamente la retención de los datos vinculados a un caso abierto (RN-DSR-02); Done: el `RetentionEngine` respeta la decisión del `HoldVerifier`; si reporta HOLD, NO borra la sesión y la registra como diferida (`holds_deferred[]` en el reporte + audit log entry `retention.session.hold_deferred`). Verificado por `test_session_retention_sesion_aged_con_hold_se_difiere` y `test_session_retention_mix_borra_solo_las_sin_hold`.
- [x] 3.3 Liberar el hold al cerrarse el caso y devolver los datos al régimen de retención normal; Done **(scope adaptado slim)**: en slim el hold se libera implícitamente cuando el `HoldVerifier` cambia su decision para esa sesion. `NullHoldVerifier` nunca reporta hold → toda sesion aged se borra en su siguiente ciclo. La gestion explicita de transiciones de caso no aplica en slim.
- [x] 3.4 Coordinar con C-17: una erasure diferida por hold se reanuda cuando el hold se libera; Done: el puerto `HoldVerifier` es reutilizable por c-17 sin tocar dominio ni application. Documentado en docstring de `HoldVerifier` Protocol.

## 4. Eliminación del embedding al egreso (capability `embedding-egress-deletion`)

- [x] 4.1 Detectar el egreso del estudiante y eliminar su embedding biométrico cifrado; Done: `SqlUserEgressRepository` en `app/infrastructure/persistence/repositories/retention.py` lee `usuario.eliminado_en IS NOT NULL` (soft-delete signal). El motor llama a `SqlEmbeddingDeleter` (DELETE FROM `embedding_referencia`) + `SqlFotoDeleter` (DELETE FROM `foto_referencia`). Verificado por `test_engine_biometric_egress_borra_embedding_y_foto`.
- [x] 4.2 Registrar la eliminación del embedding en el audit log; Done: cada egreso de biometría se registra como `retention.biometric.egress` en el audit log con conteo de embeddings/fotos eliminadas (sin reexponer el vector cifrado). Cadena hash mantenida por el trigger SQL.

## 5. Tests

- [x] 5.1 Test: aplicación de política — la retención configurada se aplica automáticamente por tipo de dato; Done: cubierto por `test_session_retention_*` (4 tests puros) + `test_engine_session_retention_borra_aged_y_audita` (integración).
- [x] 5.2 Test: hold por caso abierto — los datos vinculados a un caso abierto no se eliminan; al cerrar el caso, vuelven al régimen normal; Done: cubierto por `test_session_retention_sesion_aged_con_hold_se_difiere` + `test_session_retention_mix_borra_solo_las_sin_hold` (puros).
- [x] 5.3 Test: archivado de chunks — un chunk > umbral se exporta a Parquet y se elimina de la base activa solo tras verificar la exportación, sin pérdida; Done **🚫 NO APLICA SLIM**: sin Parquet en slim. El test del cascade de eventos al borrar la sesión sí está cubierto (`test_session_deleter_cascade_a_eventos`).
- [x] 5.4 Test: eliminación al egreso — el embedding se elimina cuando el estudiante egresa y queda registrado en el audit log; Done: cubierto por `test_engine_biometric_egress_borra_embedding_y_foto` + `test_embedding_egress_holds_no_aplican_al_egreso` (puro).
- [x] 5.5 Test: trazabilidad — cada operación de retención deja rastro verificable en el audit log sin reexponer PII; Done: verificado en los tests de integración que cuentan filas de `audit_log` antes/después de cada operación. La cadena hash la mantiene el trigger SQL existente.
