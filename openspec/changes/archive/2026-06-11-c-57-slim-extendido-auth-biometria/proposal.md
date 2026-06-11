## Why

El backend slim (`main_slim`) corre en Railway (Postgres estándar, sin TimescaleDB) y hoy solo expone proctoring sin auth. El dueño quiere TODAS las features en producción — auth JWT propia, gestión de usuarios y enrollment biométrico — pero sin montar el stack enterprise del full (Keycloak, MinIO, OTEL, Vault). Los routers de auth, users y enrollment ya existen (creados en c-55/c-56 para el full), pero no están montados en el slim ni las tablas que necesitan existen en la rama slim de Alembic.

## What Changes

- **Extender `config_slim.py` (SlimSettings)**: agregar `auth_provider`, `jwt_own_secret`, `jwt_own_issuer`, `refresh_token_ttl_seconds`, `embedding_encryption_key`. Mantener el perfil liviano: cero variables de Keycloak/MinIO/OTEL obligatorias.
- **Crear `infrastructure/auth/slim_wiring.py`**: variante de `build_jwt_validator` que solo arma el verificador HS256 (JWT propio) sin contactar el JWKS de Keycloak. El `JwtValidator` existente ya soporta modo HS256-only; solo falta un wiring que no importe `Settings` del full.
- **Nueva migración Alembic rama slim (`0008_c57_auth_biometria_slim.py`)**: cuelga de `0005` (down_revision), branch slim. Crea en tablas Postgres estándar: `usuario` (id, id_institucional, email, roles JSONB, attrs_federados JSONB, password_hash TEXT nullable, auth_provider TEXT default 'jwt'), `refresh_tokens` (id, jti, usuario_id FK CASCADE, expires_at, rotado_en, created_at), `foto_referencia` (id, usuario_id FK CASCADE, foto_bytes BYTEA, hash_sha256 TEXT, vigente BOOLEAN, created_at), `embedding_referencia` (id, usuario_id FK CASCADE, embedding_cifrado TEXT, algoritmo TEXT, fecha_captura, fecha_expiracion, vigente BOOLEAN, eliminado_en, created_at). Sin `depends_on` de la rama principal.
- **Storage de foto: DB en lugar de MinIO** — columna `foto_bytes BYTEA` en `foto_referencia` (slim). El full usa MinIO; el slim usa DB para el MVP. El enrollment router ya acepta base64; el service `GuardarFotoPerfilService` recibe un `put_fn` inyectable — se reemplaza por un callable que escribe en DB en vez de bucket.
- **Extender `main_slim.py`**: montar auth_router (`/api/v1/auth`), users_router (`/api/v1/users`), enrollment_router (`/api/v1/enrollment`). Cablear en el lifespan: `app.state.settings` (SlimSettings), `app.state.jwt_validator` (slim_wiring), `app.state.session_factory`, `app.state.profile_photo_storage` (adaptador DB), `app.state.refresh_store` (DbRefreshTokenStore).
- **Ajustar `enrollment/router.py` para ser agnóstico de `get_session`**: hoy importa `from app.infrastructure.persistence.session import get_session` (que carga `config.Settings` del full). Se reemplaza por `request.app.state.session_factory` (ya usado en el auth router).
- **Verificar y ajustar `seed_users.py`**: confirmar que corre contra el slim (tablas de la migración 0008) y que genera usuarios con password hasheado.
- **Documentar env vars nuevas del slim**: `JWT_OWN_SECRET` (obligatorio), `EMBEDDING_ENCRYPTION_KEY` (obligatorio), `JWT_OWN_ISSUER` (default `activeexam-auth`), `REFRESH_TOKEN_TTL_SECONDS` (default 604800). Para Railway dashboard.

## Capabilities

### New Capabilities

- `slim-auth-jwt`: auth JWT propia (HS256) en el backend slim — login, refresh persistente en DB, /me. Sin Keycloak.
- `slim-user-management`: creación de usuarios con credencial local en el slim (solo admin_sistema). Tabla `usuario` en rama slim.
- `slim-biometric-enrollment`: enrollment biométrico (foto en DB + embedding cifrado) en el slim. Sin MinIO.
- `slim-migration-auth-biometria`: migración Alembic rama slim que crea las 4 tablas de auth+biometría como tablas Postgres estándar, aislada de la rama principal (cero riesgo de arrastrar TimescaleDB).

### Modified Capabilities

- `exam-enrollment`: el router de enrollment hoy importa `get_session` del módulo full (`persistence.session`). Se adapta para ser agnóstico del módulo de config (tomar `session_factory` del app state en vez de importar el módulo de config del full).

## Impact

- **Archivos modificados**: `backend/app/main_slim.py`, `backend/app/config_slim.py`, `backend/app/presentation/api/v1/enrollment/router.py` (mínimo — solo la dependencia de `get_session`).
- **Archivos nuevos**: `backend/migrations/versions/0008_c57_auth_biometria_slim.py`, `backend/app/infrastructure/auth/slim_wiring.py`, `backend/app/infrastructure/storage/db_photo_storage.py` (adaptador foto→DB bytea).
- **Sin cambios en**: routers de auth/users (se reusan sin modificación), modelos SQLAlchemy (`transactional.py`), dominio, servicios de aplicación.
- **Railway**: requiere setear `JWT_OWN_SECRET` y `EMBEDDING_ENCRYPTION_KEY` en el dashboard. `alembic upgrade slim@head` aplica la 0008 automáticamente (Dockerfile.slim CMD).
- **Tests**: verificar contra `postgres:16-alpine` (SIN TimescaleDB) — mismo entorno que Railway. Incidente previo (c-55/c-56): nunca usar imagen timescale para tests del slim.
