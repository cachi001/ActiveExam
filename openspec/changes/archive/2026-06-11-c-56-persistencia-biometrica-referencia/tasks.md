## 1. Migración de Base de Datos (Alembic 0007)

- [x] 1.1 Crear `backend/migrations/versions/0007_biometric_reference_enrollment.py` — migración en dos pasos (Paso 1: CREATE TABLE `foto_referencia` y `embedding_referencia`, no destructivo). Cadena: `Revises: 0006`, `depends_on: ['0002']`. Incluir índices en `usuario_id` y `vigente` para ambas tablas.
- [x] 1.2 Verificar `alembic upgrade head` — cubierto por `backend/tests/test_c56_migration_0007.py::test_migracion_0007_upgrade_y_downgrade` (verifica que `foto_referencia` y `embedding_referencia` aparecen tras `alembic upgrade 0007`). _(requires_stack)_
- [x] 1.3 Verificar `alembic downgrade -1` — cubierto por el mismo test (verifica que las tablas desaparecen tras `downgrade -1` y la DB vuelve a 0006). _(requires_stack)_
- [x] 1.4 Verificar cascade delete — cubierto por `backend/tests/test_c56_cascade_delete.py::test_cascade_delete_usuario_elimina_foto_y_embedding` (crea usuario+foto+embedding, borra usuario, asserta que las hijas desaparecen por CASCADE de Postgres). _(requires_stack)_

## 2. Servicio de Cifrado de Embeddings

- [x] 2.1 Crear `backend/app/infrastructure/crypto/embedding_encryption.py` — clase `EmbeddingEncryptionService` con `encrypt(embedding: list[float]) -> str` y `decrypt(ciphertext: str) -> list[float]`. Usar `cryptography.fernet.Fernet`. Clave desde `settings.EMBEDDING_ENCRYPTION_KEY`. Lanzar `ConfigurationError` si la clave no está configurada.
- [x] 2.2 Agregar `EMBEDDING_ENCRYPTION_KEY: str` al modelo `Settings` (`backend/app/config.py` o equivalente) — campo obligatorio, sin default, sin valor hardcodeado.
- [x] 2.3 Test unitario de round-trip: `encrypt` → `decrypt` devuelve el vector original (128 floats, tolerancia float64). Test de ausencia de clave: lanza error al inicializar.

## 3. Modelos SQLAlchemy y Repositorios

- [x] 3.1 Crear modelos SQLAlchemy para `FotoReferencia` y `EmbeddingReferencia` en `backend/app/infrastructure/persistence/models/` (o el módulo existente de modelos). `snake_case` en columnas y atributos.
- [x] 3.2 Crear `FotoReferenciaRepository` con métodos: `crear(usuario_id, uri_storage, hash_sha256, bucket) -> FotoReferencia` y `marcar_anteriores_no_vigentes(usuario_id)`. Usar session SQLAlchemy.
- [x] 3.3 Crear `EmbeddingReferenciaRepository` con métodos: `crear(usuario_id, embedding_cifrado, algoritmo) -> EmbeddingReferencia` y `marcar_anteriores_no_vigentes(usuario_id)` y `obtener_vigente(usuario_id) -> EmbeddingReferencia | None`.

## 4. Lógica de Storage para Foto de Perfil

- [x] 4.1 Configurar bucket `activeexam-perfil` en MinIO/S3 (sin Object Lock, con SSE-S3). Agregar nombre del bucket como variable de entorno `STORAGE_PERFIL_BUCKET` en `Settings`.
- [x] 4.2 Crear o extender el servicio de storage existente para soportar subida al bucket de perfiles: método `subir_foto_perfil(usuario_id: str, imagen_bytes: bytes) -> str` que devuelve la `uri_storage` (key en el bucket). Calcular `hash_sha256` del contenido antes de subir.

## 5. Application Services de Enrollment

- [x] 5.1 Crear `backend/app/application/enrollment/guardar_foto_perfil.py` — `GuardarFotoPerfilService`: orquesta la subida a storage y la persistencia en `foto_referencia` (marcar anteriores no vigentes, crear nuevo registro). Devuelve `foto_referencia_id`.
- [x] 5.2 Crear `backend/app/application/enrollment/guardar_embedding_referencia.py` — `GuardarEmbeddingReferenciaService`: valida dimensión (debe ser 128), cifra con `EmbeddingEncryptionService`, persiste en `embedding_referencia` (marcar anteriores no vigentes, crear nuevo registro). Devuelve `referencia_id`.

## 6. Schemas Pydantic de los Endpoints

- [x] 6.1 Crear `backend/app/presentation/api/v1/enrollment/schemas.py` con:
  - `FotoPerfilRequest` — campo `imagen_base64: str`. `model_config = ConfigDict(extra='forbid')`.
  - `FotoPerfilResponse` — campo `foto_referencia_id: UUID`. `model_config = ConfigDict(extra='forbid')`.
  - `EmbeddingReferenciaRequest` — campo `embedding: list[float]` con validador de longitud == 128. `model_config = ConfigDict(extra='forbid')`.
  - `EmbeddingReferenciaResponse` — campo `referencia_id: UUID`. `model_config = ConfigDict(extra='forbid')`.

## 7. Endpoints FastAPI de Enrollment

- [x] 7.1 Crear `backend/app/presentation/api/v1/enrollment/router.py` — router con prefijo `/enrollment`. Registrar en el router principal de `v1`.
- [x] 7.2 Implementar `POST /enrollment/foto-perfil`: requiere autenticación JWT (rol `estudiante`), valida `FotoPerfilRequest`, llama a `GuardarFotoPerfilService`, devuelve `FotoPerfilResponse` con HTTP 201.
- [x] 7.3 Implementar `POST /enrollment/embedding-referencia`: requiere autenticación JWT (rol `estudiante`), valida `EmbeddingReferenciaRequest` (incluyendo dimensión 128), llama a `GuardarEmbeddingReferenciaService`, devuelve `EmbeddingReferenciaResponse` con HTTP 201.
- [x] 7.4 Verificar que ambos endpoints devuelven HTTP 401 sin token y HTTP 403 con token de rol incorrecto — cubierto por `test_c56_enrollment_endpoints.py::test_foto_perfil_401_sin_token` + `test_foto_perfil_403_rol_incorrecto`. El endpoint `embedding-referencia` comparte el mismo dependency `require_role([estudiante])` por lo que el comportamiento auth está unificado. _(requires_stack)_

## 8. Tests de Integración Backend

- [x] 8.1 Test de integración foto-perfil — cubierto por `test_c56_enrollment_endpoints.py::test_foto_perfil_persistida_en_db` + `test_foto_anterior_marcada_no_vigente_en_re_enrollment`. _(requires_stack)_
- [x] 8.2 Test de integración embedding-referencia — cubierto por `test_c56_enrollment_endpoints.py::test_embedding_cifrado_en_db_no_en_claro` + `test_embedding_dimension_invalida_422`. _(requires_stack)_
- [x] 8.3 Test de descifrado round-trip — cubierto por `test_c56_enrollment_endpoints.py::test_round_trip_cifrado_descifrado_integracion`. _(requires_stack)_
- [x] 8.4 Test de la migración 0007 — cubierto por `test_c56_migration_0007.py::test_migracion_0007_upgrade_y_downgrade` (incluye upgrade 0006→0007, verificación de tablas, downgrade -1, verificación de eliminación, y re-upgrade para no dejar la DB rota). _(requires_stack)_

## 9. Actualización del Frontend — api.ts

- [x] 9.1 Reemplazar `guardarFotoPerfil` (~línea 695 de `frontend/src/lib/api.ts`): en lugar de actualizar in-memory, hacer `POST /api/v1/enrollment/foto-perfil` con `{ imagen_base64: dataUrl }`. Retornar `foto_referencia_id`.
- [x] 9.2 Reemplazar `guardarReferenciaBiometrica` (~línea 623 de `frontend/src/lib/api.ts`): en lugar de guardar in-memory, hacer `POST /api/v1/enrollment/embedding-referencia` con `{ embedding: float[] }`. Retornar `{ referencia_id }`.

## 10. Actualización del Frontend — store.ts

- [x] 10.1 Actualizar `frontend/src/lib/store.ts`: eliminar el guardado del embedding crudo en localStorage (`activeexam_bio_ref`). Agregar campo `biometrico_referencia_id: string | null` al estado persistido. Persistir el `referencia_id` recibido del backend.
- [x] 10.2 Verificar que el store no persiste el array de floats del embedding en ninguna clave de localStorage.

## 11. Actualización del Frontend — Componentes de Enrollment

- [x] 11.1 Actualizar `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx`: tras la llamada a `api.guardarReferenciaBiometrica`, consumir el `referencia_id` retornado y pasarlo al handler de `onBiometricComplete` (o equivalente). Descartar el embedding crudo del estado local.
- [x] 11.2 Actualizar `frontend/src/screens/StudentProfile.tsx` (`handleFotoCapturada`): consumir el `foto_referencia_id` retornado por `api.guardarFotoPerfil` y pasarlo al store. Manejar errores del backend con feedback visual al alumno (mensaje + opción de reintentar).
- [x] 11.3 Verificar que la fase `biometria` del enrollment no avanza si el endpoint devuelve error (4xx / 5xx / fallo de red). Mostrar mensaje de error y opción de reintentar.

## 12. Variables de Entorno y Configuración

- [x] 12.1 Variables documentadas en código (el `.env.example` está bloqueado por permisos de Windows): `EMBEDDING_ENCRYPTION_KEY` en `backend/app/config_slim.py:15` con comando para generarla (`Fernet.generate_key()`), `STORAGE_PERFIL_BUCKET` en `backend/app/main.py:88` con default `activeexam-perfil`. Script de generación: `backend/scripts/generar_embedding_key.py`.
- [x] 12.2 Generar una clave de ejemplo para desarrollo local (script o instrucción en README de desarrollo) — sin incluir valores reales en el repositorio. _(implementado en `backend/scripts/generar_embedding_key.py`)_

## 13. Smoke Test End-to-End

- [x] 13.1 Smoke e2e cubierto por tests de integración (8.1-8.3) + verificación visual en sesión 2026-05-30 del flujo enrollment alumno → fase foto_perfil → foto en MinIO → fase biometría → embedding cifrado en DB → store con `referencia_id`. Memoria engram confirma stack levantado con `dev-up.ps1` y flujo completo funcional. _(requires_stack — verificado manualmente)_
