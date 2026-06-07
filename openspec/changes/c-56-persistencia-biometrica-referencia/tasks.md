## 1. Migración de Base de Datos (Alembic 0007)

- [x] 1.1 Crear `backend/migrations/versions/0007_biometric_reference_enrollment.py` — migración en dos pasos (Paso 1: CREATE TABLE `foto_referencia` y `embedding_referencia`, no destructivo). Cadena: `Revises: 0006`, `depends_on: ['0002']`. Incluir índices en `usuario_id` y `vigente` para ambas tablas.
- [ ] 1.2 Verificar `alembic upgrade head` sobre DB de test con revisiones 0001–0006 aplicadas — las dos tablas nuevas deben crearse sin errores de constraint. _(requires_stack)_
- [ ] 1.3 Verificar `alembic downgrade -1` — las dos tablas se eliminan limpiamente y la DB queda en revisión 0006 sin afectar otras tablas. _(requires_stack)_
- [ ] 1.4 Verificar cascade delete: al borrar un `usuario`, los registros de `foto_referencia` y `embedding_referencia` se eliminan automáticamente. _(requires_stack)_

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
- [ ] 7.4 Verificar que ambos endpoints devuelven HTTP 401 sin token y HTTP 403 con token de rol incorrecto. _(requires_stack)_

## 8. Tests de Integración Backend

- [ ] 8.1 Test de integración para `POST /enrollment/foto-perfil` (testcontainers / DB efímera): foto subida, metadatos en DB, `foto_referencia_id` en response, foto anterior marcada no vigente en re-enrollment. _(requires_stack)_
- [ ] 8.2 Test de integración para `POST /enrollment/embedding-referencia` (testcontainers / DB efímera): embedding cifrado en DB (no en claro), `referencia_id` en response, embedding anterior marcado no vigente en re-enrollment, rechazo de vector con dimensión != 128. _(requires_stack)_
- [ ] 8.3 Test de descifrado: leer `embedding_cifrado` de la DB y descifrarlo con `EmbeddingEncryptionService.decrypt()` — verificar que el vector resultante coincide con el enviado (round-trip de integración completo). _(requires_stack)_
- [ ] 8.4 Test de la migración 0007: upgrade desde 0006 y downgrade de vuelta (con testcontainers). _(requires_stack)_

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

- [ ] 12.1 Documentar en `.env.example` (o equivalente) las variables nuevas: `EMBEDDING_ENCRYPTION_KEY` (32 bytes en base64-urlsafe), `STORAGE_PERFIL_BUCKET` (default: `activeexam-perfil`). _(pendiente: permisos de archivo en Windows)_
- [x] 12.2 Generar una clave de ejemplo para desarrollo local (script o instrucción en README de desarrollo) — sin incluir valores reales en el repositorio. _(implementado en `backend/scripts/generar_embedding_key.py`)_

## 13. Smoke Test End-to-End

- [ ] 13.1 Verificar manualmente (o con test e2e) el flujo completo: alumno autenticado (c-55) → fase `foto_perfil` → foto persistida en MinIO → fase `biometria` → embedding cifrado en DB → store tiene `referencia_id` (no embedding crudo) → gate `puedeRendir` evalúa referencia biométrica en backend. _(requires_stack — manual con full stack)_
