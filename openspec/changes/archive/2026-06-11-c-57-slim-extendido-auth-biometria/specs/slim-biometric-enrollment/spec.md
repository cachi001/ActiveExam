## ADDED Requirements

### Requirement: main_slim monta enrollment_router

`main_slim.py` SHALL montar el router de enrollment (`presentation/api/v1/enrollment/router.py`) en `/api/v1/enrollment`. El router SHALL obtener la `session_factory` de `request.app.state.session_factory` (no del módulo `persistence.session` del full). `app.state.profile_photo_storage` SHALL ser un adaptador que persista la foto en DB (BYTEA).

#### Scenario: POST /api/v1/enrollment/foto-perfil por estudiante autenticado
- **WHEN** un estudiante autenticado (Bearer JWT HS256) hace `POST /api/v1/enrollment/foto-perfil` con `imagen_base64` válida (<=500 KB decodificada)
- **THEN** la respuesta es 201 con `foto_referencia_id` y la foto queda persistida en `foto_referencia.foto_bytes` (BYTEA) en DB

#### Scenario: foto demasiado grande es rechazada
- **WHEN** el payload de `imagen_base64` decodifica a más de 500 KB
- **THEN** la respuesta es 422

#### Scenario: POST /api/v1/enrollment/embedding-referencia por estudiante autenticado
- **WHEN** un estudiante autenticado hace `POST /api/v1/enrollment/embedding-referencia` con un vector de 128 floats
- **THEN** la respuesta es 201 con `referencia_id` y el embedding queda cifrado con Fernet (EMBEDDING_ENCRYPTION_KEY) en `embedding_referencia.embedding_cifrado`

#### Scenario: embedding con dimensión incorrecta es rechazado
- **WHEN** el vector tiene diferente cantidad de dimensiones a 128
- **THEN** la respuesta es 422

### Requirement: tablas foto_referencia y embedding_referencia existen en la rama slim

La migración `0008` SHALL crear:
- `foto_referencia`: columnas `id UUID PK`, `usuario_id UUID FK→usuario.id CASCADE DELETE`, `foto_bytes BYTEA NOT NULL`, `hash_sha256 TEXT NOT NULL`, `vigente BOOLEAN NOT NULL DEFAULT true`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `embedding_referencia`: columnas `id UUID PK`, `usuario_id UUID FK→usuario.id CASCADE DELETE`, `embedding_cifrado TEXT NOT NULL`, `algoritmo TEXT NOT NULL DEFAULT 'face-api-128d'`, `fecha_captura TIMESTAMPTZ NOT NULL DEFAULT now()`, `fecha_expiracion TIMESTAMPTZ NULL`, `vigente BOOLEAN NOT NULL DEFAULT true`, `eliminado_en TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

#### Scenario: alembic upgrade slim@head crea tablas biométricas sin error
- **WHEN** se ejecuta `alembic upgrade slim@head` contra postgres:16-alpine
- **THEN** las tablas `foto_referencia` y `embedding_referencia` existen con FK a `usuario.id`

### Requirement: db_photo_storage — adaptador foto en DB BYTEA

SHALL existir `backend/app/infrastructure/storage/db_photo_storage.py` con un servicio o callable que persista la foto en la columna `foto_bytes` BYTEA de `foto_referencia`, compatible con la interfaz que espera el enrollment router (reemplaza MinIO en el slim).

#### Scenario: foto se persiste en BYTEA y se recupera con integridad
- **WHEN** se guarda una foto via el adaptador DB
- **THEN** el hash SHA-256 del blob recuperado coincide con el hash calculado al guardar

### Requirement: GuardarFotoPerfilSlimService persiste en DB sin MinIO

SHALL existir un servicio de aplicación `GuardarFotoPerfilSlimService` (o equivalente) que reciba el `usuario_id` y `imagen_base64`, valide el tamaño, calcule el hash, y persista directamente en `foto_referencia.foto_bytes` (BYTEA). No usa `put_fn` de MinIO ni `uri_storage`.

#### Scenario: servicio persiste foto y marca vigente=true
- **WHEN** se llama al servicio con un `usuario_id` y `imagen_base64` válido
- **THEN** se crea una fila en `foto_referencia` con `foto_bytes` not null, `vigente=true` y `hash_sha256` correcto
