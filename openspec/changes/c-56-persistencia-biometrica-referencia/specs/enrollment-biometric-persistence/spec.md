## ADDED Requirements

### Requirement: El backend persiste la foto de perfil del alumno en storage seguro
El sistema SHALL proveer el endpoint `POST /api/v1/enrollment/foto-perfil` que reciba la imagen capturada en el enrollment (formato base64 o multipart), la suba al bucket de perfiles (`activeexam-perfil`, no-WORM, con cifrado SSE-S3), y persista los metadatos (`uri_storage`, `hash_sha256`, `bucket`, `usuario_id`, timestamps) en la tabla `foto_referencia`. El endpoint SHALL ser accesible únicamente por el alumno autenticado (rol `estudiante`). El sistema SHALL devolver el `foto_referencia_id` (UUID) al cliente.

#### Scenario: Foto subida y metadatos persistidos exitosamente
- **WHEN** el alumno autenticado hace `POST /api/v1/enrollment/foto-perfil` con una imagen válida
- **THEN** la imagen se sube al bucket `activeexam-perfil` con cifrado SSE-S3
- **THEN** se persiste un registro en `foto_referencia` con `usuario_id` del token, `hash_sha256` del contenido, `uri_storage`, `vigente = TRUE`
- **THEN** el endpoint devuelve `{ foto_referencia_id: "<uuid>" }` con HTTP 201

#### Scenario: Foto anterior marcada como no vigente al subir una nueva
- **WHEN** el alumno ya tiene un registro `vigente = TRUE` en `foto_referencia` y sube una nueva foto
- **THEN** el registro anterior es marcado `vigente = FALSE`
- **THEN** el nuevo registro es creado con `vigente = TRUE`
- **THEN** el endpoint devuelve el nuevo `foto_referencia_id`

#### Scenario: Intento sin autenticación rechazado
- **WHEN** se llama a `POST /api/v1/enrollment/foto-perfil` sin token JWT válido
- **THEN** el endpoint devuelve HTTP 401

#### Scenario: Intento de otro usuario rechazado
- **WHEN** un usuario con rol distinto de `estudiante` (o con `usuario_id` distinto al del token) llama al endpoint
- **THEN** el endpoint devuelve HTTP 403

---

### Requirement: El backend persiste el embedding biométrico de referencia cifrado at-rest
El sistema SHALL proveer el endpoint `POST /api/v1/enrollment/embedding-referencia` que reciba el embedding 128-d (array de floats) calculado client-side durante el enrollment. El backend SHALL cifrar el embedding con Fernet (clave maestra `EMBEDDING_ENCRYPTION_KEY`) antes de persistirlo en la tabla `embedding_referencia`. El endpoint SHALL devolver un `referencia_id` (UUID) opaco al cliente. El embedding crudo jamás deberá persistirse sin cifrar.

#### Scenario: Embedding cifrado y persistido exitosamente
- **WHEN** el alumno autenticado hace `POST /api/v1/enrollment/embedding-referencia` con un array de 128 floats válido
- **THEN** el backend cifra el embedding con Fernet usando `EMBEDDING_ENCRYPTION_KEY`
- **THEN** persiste en `embedding_referencia`: `usuario_id`, `embedding_cifrado` (ciphertext), `algoritmo = 'face-api-128d'`, `vigente = TRUE`, `fecha_captura = now()`
- **THEN** devuelve `{ referencia_id: "<uuid>" }` con HTTP 201

#### Scenario: Embedding anterior marcado como no vigente
- **WHEN** el alumno ya tiene un embedding `vigente = TRUE` y envía uno nuevo
- **THEN** el embedding anterior es marcado `vigente = FALSE`
- **THEN** el nuevo embedding es creado con `vigente = TRUE` y un nuevo `referencia_id`

#### Scenario: Vector con dimensión incorrecta rechazado
- **WHEN** el cliente envía un array con un número de dimensiones distinto de 128
- **THEN** el endpoint devuelve HTTP 422 con mensaje de validación descriptivo

#### Scenario: Descifrado correcto del embedding persistido
- **WHEN** el backend necesita leer el embedding de referencia para comparación 1:1 (C-09)
- **THEN** el `EmbeddingEncryptionService.decrypt()` devuelve exactamente el mismo array de 128 floats que fue cifrado
- **THEN** el round-trip cifrado/descifrado es verificable mediante test de integración

#### Scenario: Intento sin autenticación rechazado
- **WHEN** se llama a `POST /api/v1/enrollment/embedding-referencia` sin token JWT válido
- **THEN** el endpoint devuelve HTTP 401

---

### Requirement: El schema de la base de datos incluye las tablas de referencia biométrica
El sistema SHALL crear las tablas `foto_referencia` y `embedding_referencia` mediante migración Alembic 0007, en dos pasos (no destructivo). Ambas tablas SHALL tener FK a `usuario(id)` con `ON DELETE CASCADE`. La migración SHALL soportar `upgrade` y `downgrade` sin afectar datos existentes.

#### Scenario: Migración upgrade exitosa en DB limpia
- **WHEN** se ejecuta `alembic upgrade head` sobre una DB que tiene hasta revisión 0006
- **THEN** se crean las tablas `foto_referencia` y `embedding_referencia` con todas sus columnas e índices
- **THEN** no hay errores de constraint ni conflicto con tablas existentes

#### Scenario: Migración downgrade limpia
- **WHEN** se ejecuta `alembic downgrade -1` estando en revisión 0007
- **THEN** se eliminan las tablas `foto_referencia` y `embedding_referencia` sin afectar otras tablas
- **THEN** la DB queda en el estado de revisión 0006

#### Scenario: Cascade delete al borrar usuario
- **WHEN** se elimina un registro de `usuario`
- **THEN** todos los registros de `foto_referencia` y `embedding_referencia` asociados al `usuario_id` son eliminados en cascada

---

### Requirement: El servicio de cifrado de embeddings provee un round-trip verificable
El sistema SHALL implementar `EmbeddingEncryptionService` con métodos `encrypt(embedding: list[float]) -> str` y `decrypt(ciphertext: str) -> list[float]`. La clave maestra SHALL ser inyectada desde la variable de entorno `EMBEDDING_ENCRYPTION_KEY` (nunca hardcodeada). Si la variable no está configurada, el servicio SHALL lanzar un error de configuración al inicializarse.

#### Scenario: Cifrado produce ciphertext distinto al vector original
- **WHEN** `EmbeddingEncryptionService.encrypt([0.1, 0.2, ..., 0.128])` es invocado
- **THEN** el resultado es un string base64-urlsafe (Fernet token) distinto al vector serializado en claro

#### Scenario: Descifrado del ciphertext devuelve el vector original
- **WHEN** `EmbeddingEncryptionService.decrypt(ciphertext)` es invocado con el resultado de `encrypt`
- **THEN** devuelve exactamente la misma lista de 128 floats original (con tolerancia de precisión float64)

#### Scenario: Ausencia de clave de entorno lanza error al iniciar
- **WHEN** `EMBEDDING_ENCRYPTION_KEY` no está definida en el entorno
- **THEN** la inicialización de `EmbeddingEncryptionService` lanza `ConfigurationError` (o equivalente) antes de aceptar cualquier llamada
