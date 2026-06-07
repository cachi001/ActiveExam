## 1. Migración Alembic rama slim (0008)

- [x] 1.1 Crear `backend/migrations/versions/0008_c57_auth_biometria_slim.py` con `down_revision="0005"`, `branch_labels=None`, `depends_on=None`
- [x] 1.2 Implementar `upgrade()`: CREATE TABLE `usuario` (id, id_institucional UNIQUE, email, roles JSONB, attrs_federados JSONB, password_hash TEXT nullable, auth_provider TEXT DEFAULT 'jwt') con pgcrypto para gen_random_uuid()
- [x] 1.3 Implementar en `upgrade()`: CREATE TABLE `refresh_tokens` (id, jti TEXT UNIQUE, usuario_id FK→usuario.id CASCADE, expires_at, rotado_en, created_at) con índices en jti (unique), usuario_id y expires_at
- [x] 1.4 Implementar en `upgrade()`: CREATE TABLE `foto_referencia` (id, usuario_id FK→usuario.id CASCADE, foto_bytes BYTEA NOT NULL, hash_sha256 TEXT NOT NULL, vigente BOOLEAN DEFAULT true, created_at, updated_at) con índices en usuario_id y vigente
- [x] 1.5 Implementar en `upgrade()`: CREATE TABLE `embedding_referencia` (id, usuario_id FK→usuario.id CASCADE, embedding_cifrado TEXT NOT NULL, algoritmo TEXT DEFAULT 'face-api-128d', fecha_captura, fecha_expiracion nullable, vigente BOOLEAN DEFAULT true, eliminado_en nullable, created_at) con índices en usuario_id y vigente
- [x] 1.6 Implementar `downgrade()`: DROP TABLE en orden inverso (embedding_referencia → foto_referencia → refresh_tokens → usuario)
- [x] 1.7 Verificar con `alembic history` que la migración 0008 figura en la rama slim (no en la principal) y que `alembic upgrade slim@head` desde cero aplica solo 0005 → 0008 contra `postgres:16-alpine`

## 2. Config slim extendida

- [x] 2.1 Agregar a `SlimSettings` en `backend/app/config_slim.py`: `auth_provider: str = "jwt"`, `jwt_own_secret: str` (obligatorio, sin default), `jwt_own_issuer: str = "activeexam-auth"`, `jwt_audience: str = "activeexam"`, `access_token_ttl_seconds: int = 900`, `refresh_token_ttl_seconds: int = 604800`, `embedding_encryption_key: str` (obligatorio, sin default)
- [x] 2.2 Verificar que `SlimSettings` mantiene `model_config = SettingsConfigDict(..., extra="forbid")` y que falla con `ValidationError` explícito si faltan `jwt_own_secret` o `embedding_encryption_key`
- [x] 2.3 Test unitario: `SlimSettings(database_url=..., frontend_origin=...)` sin jwt_own_secret lanza `ValidationError`

## 3. slim_wiring.py — JwtValidator HS256-only

- [x] 3.1 Crear `backend/app/infrastructure/auth/slim_wiring.py` con función `build_slim_jwt_validator(settings: SlimSettings) -> JwtValidator`
- [x] 3.2 En `build_slim_jwt_validator`: construir `verify_fn_hs256` usando `build_hs256_verify_production(settings.jwt_own_secret)` (ya existe en `verifiers.py`)
- [x] 3.3 Verificar si `JwtValidator` acepta `jwks_cache=None` sin crash en el path HS256; si no, inyectar un `JwksCache` stub que lanza `NotImplementedError` en el fetch (nunca llamado en HS256)
- [x] 3.4 Construir `TokenPolicy` con `issuers_aceptados=frozenset({settings.jwt_own_issuer})`, `audience=settings.jwt_audience`
- [x] 3.5 Instanciar `JwtValidator(jwks_cache=..., policy=policy, verify_fn=None, verify_fn_hs256=verify_fn_hs256, own_issuer=settings.jwt_own_issuer, keycloak_issuer=None)`
- [x] 3.6 Test unitario: token HS256 válido es aceptado; token con secreto incorrecto lanza `UnauthenticatedError`

## 4. db_photo_storage.py — adaptador foto en DB BYTEA

- [x] 4.1 Crear `backend/app/infrastructure/storage/db_photo_storage.py`
- [x] 4.2 Implementar `DbPhotoStorageService` con método `async def guardar(session, usuario_id, imagen_base64) -> str` que: decodifica base64, valida tamaño (<=500 KB, lanza ValueError si excede), calcula SHA-256, inserta en `foto_referencia` (foto_bytes BYTEA, hash_sha256, vigente=True, usuario_id), marca previas como vigente=False, retorna el UUID creado
- [x] 4.3 Usar el modelo `FotoReferenciaModel` de `transactional.py` — si no tiene la columna `foto_bytes`, documentarlo como blocker (el modelo SQLAlchemy debe matchear la migración 0008, no la 0007 del full). RESUELTO: se usa SQLAlchemy Core SQL (`text()`) para evitar conflicto de MetaData entre el full (uri_storage/bucket) y el slim (foto_bytes BYTEA). Ver `db_photo_storage.py`.
- [x] 4.4 Test de integración contra `postgres:16-alpine`: guardar foto → verificar hash_sha256 en DB; guardar segunda foto → verificar que la primera queda vigente=False

## 5. GuardarFotoPerfilSlimService (service de aplicación)

- [x] 5.1 Crear `backend/app/application/enrollment/guardar_foto_perfil_slim.py` con `GuardarFotoPerfilSlimService`
- [x] 5.2 El servicio recibe `session: AsyncSession` (no put_fn de MinIO), valida tamaño, calcula hash, persiste en `foto_referencia.foto_bytes` usando el `DbPhotoStorageService`
- [x] 5.3 Test de integración: flujo completo via el servicio contra DB real

## 6. Ajuste enrollment/router.py (compatibilidad slim)

- [x] 6.1 En `enrollment/router.py`, reemplazar el import `from app.infrastructure.persistence.session import get_session` por una función helper `_get_session_factory(request) -> async_sessionmaker` que lea `request.app.state.session_factory`
- [x] 6.2 Si la factory es None, lanzar `HTTPException(500, "Subsistema de persistencia no inicializado.")`
- [x] 6.3 En `guardar_foto_perfil`, usar `GuardarFotoPerfilSlimService` cuando `app.state` indique que el storage es DB (o detectar el tipo del `profile_photo_storage` del state)
- [x] 6.4 Verificar que el full (main.py) sigue funcionando: `create_app()` ya cablea `app.state.session_factory` — el cambio debe ser retrocompatible
- [x] 6.5 Test de integración: `POST /enrollment/foto-perfil` en el slim retorna 201 con foto en DB

## 7. Extender main_slim.py

- [x] 7.1 En `create_slim_app()`, asignar `app.state.settings = settings` (SlimSettings ya extendida)
- [x] 7.2 Cablear `app.state.jwt_validator = build_slim_jwt_validator(settings)` usando el slim_wiring
- [x] 7.3 Cablear `app.state.session_factory = session_factory` (la slim session factory ya creada para proctoring)
- [x] 7.4 Cablear `app.state.refresh_store` con `DbRefreshTokenStore` (importar de `infrastructure/auth/db_refresh_store.py`)
- [x] 7.5 Cablear `app.state.profile_photo_storage = DbPhotoStorageService(...)` (adaptador DB)
- [x] 7.6 Importar y montar `auth_router` en `/api/v1/auth` (desde `presentation/api/v1/auth/router.py`)
- [x] 7.7 Importar y montar `users_router` en `/api/v1/users` (desde `presentation/api/v1/users/router.py`)
- [x] 7.8 Importar y montar `enrollment_router` en `/api/v1/enrollment` (desde `presentation/api/v1/enrollment/router.py`)
- [x] 7.9 Verificar que el lifespan cierra `engine.dispose()` correctamente con los 4 routers montados

## 8. Modelos SQLAlchemy — verificar compatibilidad con migración 0008

- [x] 8.1 Verificar que `UsuarioModel` en `transactional.py` tiene los campos: `id`, `id_institucional`, `email`, `roles`, `attrs_federados`, `password_hash`, `auth_provider` — deben matchear las columnas de la tabla creada en 0008
- [x] 8.2 Verificar que `RefreshTokenModel` tiene: `id`, `jti`, `usuario_id`, `expires_at`, `rotado_en`, `created_at`
- [x] 8.3 Verificar o crear `FotoReferenciaSlimModel` (o adaptar `FotoReferenciaModel` existente): debe tener `foto_bytes: Mapped[bytes]` en lugar de `uri_storage`/`bucket`. RESUELTO: creado `transactional_slim.py` con `FotoReferenciaSlimModel` + `extend_existing=True`; db_photo_storage usa Core SQL para evitar el conflicto en producción.
- [x] 8.4 Verificar que `EmbeddingReferenciaModel` matchea las columnas de 0008 slim

## 9. seed_users.py — compatibilidad slim

- [x] 9.1 Revisar `backend/scripts/seed_users.py`: verificar si importa `get_settings()` del full (`app.config`) o si acepta `DATABASE_URL` del entorno directamente
- [x] 9.2 Si importa `app.config.Settings`: refactorizar para aceptar `DATABASE_URL` como argumento de entorno o `--slim` flag, usando una conexión directa o `SlimSettings`
- [x] 9.3 Verificar que el seed inserta en la tabla `usuario` con `auth_provider='jwt'` y `password_hash` correcto (bcrypt)
- [x] 9.4 Test manual: ejecutar seed contra `postgres:16-alpine` con rama slim@head aplicada → seed inserta 3 usuarios → login con cada rol retorna 200

## 10. Tests de integración E2E slim

- [x] 10.1 Crear `backend/tests/integration/test_slim_auth_e2e.py`: test completo login → refresh → /me contra `postgres:16-alpine` (fixture `testcontainers` sin timescaledb)
- [x] 10.2 Crear `backend/tests/integration/test_slim_users_e2e.py`: test crear usuario como admin → login con ese usuario
- [x] 10.3 Crear `backend/tests/integration/test_slim_enrollment_e2e.py`: test foto-perfil + embedding-referencia como estudiante
- [x] 10.4 Verificar que NINGÚN test del slim importa de `app.config.Settings` (grep: `from app.config import`) — si alguno lo hace, es un bug
- [x] 10.5 Correr todos los tests del slim contra `postgres:16-alpine` (NO usar imagen `timescale/timescaledb`) — CRÍTICO: mismo entorno que Railway

## 11. Documentación de env vars para Railway

- [x] 11.1 Documentar en `backend/README.md` o en un archivo `docs/deploy-railway-slim.md` las env vars requeridas para el slim: `DATABASE_URL`, `FRONTEND_ORIGIN`, `JWT_OWN_SECRET`, `EMBEDDING_ENCRYPTION_KEY`, y las opcionales con sus defaults: `JWT_OWN_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`, `PORT`
- [x] 11.2 Documentar el valor de `JWT_OWN_SECRET`: debe ser un string aleatorio seguro (>=32 bytes). Incluir ejemplo de cómo generarlo: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [x] 11.3 Documentar el valor de `EMBEDDING_ENCRYPTION_KEY`: debe ser una clave Fernet válida. Incluir ejemplo: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
