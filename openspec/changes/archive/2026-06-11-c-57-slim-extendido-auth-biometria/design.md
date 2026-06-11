## Context

El backend slim (`main_slim.py`) fue creado en c-45 como un módulo deployable en Railway (Postgres estándar, sin TimescaleDB). Hoy solo monta el router de proctoring. Los changes c-55 (auth JWT propia) y c-56 (biometría de referencia) implementaron routers, servicios y migraciones para el full (`main.py`), pero las migraciones 0006 y 0007 fueron movidas a la rama principal de Alembic (no slim) para evitar arrastrar TimescaleDB (incidente Railway documentado). El resultado: Railway tiene proctoring funcional pero sin login, sin gestión de usuarios y sin enrollment biométrico.

El dueño quiere todo el producto en Railway en forma simple. La restricción dura: Railway corre Postgres estándar (`postgres:16-alpine`) — sin `CREATE EXTENSION timescaledb`. El slim debe mantenerse liviano: cero dependencias en Keycloak, MinIO, Vault ni OTEL.

**Dependencias clave identificadas** (blocker analysis):

1. `auth/wiring.py` importa `Settings` del full (requiere `keycloak_jwks_url`, `keycloak_issuer`, etc.). → Necesita `slim_wiring.py` independiente.
2. `auth/dependencies.py` lee `request.app.state.jwt_validator` → el slim debe cablear este state.
3. `enrollment/router.py` importa `from app.infrastructure.persistence.session import get_session` → ese módulo llama `get_settings()` del full (ImportError en slim si no hay las 9 vars obligatorias). → Requiere un ajuste mínimo en enrollment router para tomar la factory del app state.
4. `foto_referencia` del full tiene columna `uri_storage` + `bucket` (punteros a MinIO). El slim necesita storage en DB (columna `foto_bytes BYTEA`). → La migración slim define la tabla con schema diferente al full.

## Goals / Non-Goals

**Goals:**
- Montar auth JWT (login, refresh, /me), users (crear usuario) y enrollment (foto en DB + embedding cifrado) en el slim de Railway.
- Crear la migración Alembic en la rama slim (cuelga de 0005, sin tocar la rama principal) que crea las 4 tablas en Postgres estándar.
- Hacer que `main_slim.py` cablee correctamente el state para que los routers existentes funcionen sin modificación estructural.
- Ajustar mínimamente `enrollment/router.py` para ser agnóstico del módulo de config del full.
- Documentar las env vars nuevas para Railway.

**Non-Goals:**
- Reescribir los routers de auth, users o enrollment — se reusan tal cual.
- Agregar MinIO, Keycloak, Vault, OTEL, TimescaleDB ni Redis al slim.
- CRUD completo de usuarios (out of scope — solo creación por admin).
- Re-inferencia server-side del embedding en enrollment (D3 de c-56 — aplica en el examen, no en enrollment).
- Migrar la rama principal — las tablas del full (0006, 0007) quedan donde están.

## Decisions

### D1 — Storage de foto: DB (BYTEA) en el slim, MinIO en el full

**Decisión**: En el slim, `foto_referencia` almacena la foto en columna `foto_bytes BYTEA` directamente en Postgres. El full sigue usando MinIO.

**Alternativas consideradas**:
- Diferir la foto y persistir solo el embedding (más simple, pero el enrollment quedaría incompleto: sin foto de referencia no hay verificación 1:1 visual).
- Usar un bucket S3 público (agregar complejidad de credenciales, fuera del perfil slim).

**Rationale**: Para el MVP en Railway, Postgres ya está disponible. BYTEA hasta ~5 MB es viable (foto de perfil comprimida). No requiere servicio adicional. El schema de `foto_referencia` del slim difiere del full (no tiene `uri_storage`/`bucket`) — esto es intencional y documentado.

**Trade-off**: Si en el futuro el slim crece, migrar de BYTEA a S3 requiere una migración Alembic que añada las columnas `uri_storage`/`bucket` y un data-migration para mover los bytes. Asumible para MVP.

### D2 — Migración slim independiente (0008, down_revision=0005, sin depends_on de la rama principal)

**Decisión**: Crear `0008_c57_auth_biometria_slim.py` con `down_revision="0005"`, `branch_labels=None`, `depends_on=None`. Esto garantiza que `alembic upgrade slim@head` aplique 0005 → 0008 sin tocar ninguna migración de la rama principal.

**Rationale**: El incidente Railway de c-55/c-56 demostró que cualquier `depends_on` a la rama principal arrastra la 0001 (`CREATE EXTENSION timescaledb`) y rompe el deploy. La solución: las tablas de auth y biometría se crean desde cero en la migración slim, sin referenciar las definiciones de 0006/0007 de la rama principal.

**Consecuencia**: la tabla `usuario` existirá dos veces en la historia de Alembic (una en 0002 de la rama principal, otra en 0008 de la rama slim). Son independientes. El ORM funciona igual porque `UsuarioModel` mapea a la misma tabla física (`usuario`) en ambas ramas; en Railway solo existe la rama slim.

### D3 — slim_wiring.py: JwtValidator HS256-only sin Keycloak

**Decisión**: Crear `backend/app/infrastructure/auth/slim_wiring.py` con `build_slim_jwt_validator(settings: SlimSettings) -> JwtValidator`. Construye el validator con solo el verificador HS256 (secreto de `settings.jwt_own_secret`). No fetcha JWKS, no requiere `keycloak_issuer`.

**Rationale**: `auth/wiring.py` importa `Settings` del full y requiere `keycloak_jwks_url`. Importarlo en `main_slim.py` forzaría declarar las 9+ variables obligatorias del full. El `JwtValidator` existente ya acepta `verify_fn_hs256` sin `jwks_cache` activo — solo hay que construirlo correctamente.

**Implementación**: `slim_wiring.py` usa `build_hs256_verify_production(settings.jwt_own_secret)` (ya existe en `verifiers.py`) y arma el `JwtValidator` con `jwks_cache=None` (o un cache stub no-op) y `own_issuer=settings.jwt_own_issuer`.

### D4 — Ajuste mínimo en enrollment/router.py: eliminar import de `persistence.session`

**Decisión**: El enrollment router importa `from app.infrastructure.persistence.session import get_session` que transitivamente llama `get_settings()` del full. Se reemplaza el import por tomar la `session_factory` del `request.app.state` (mismo patrón que el auth router).

**Rationale**: Es el cambio mínimo necesario para que el router sea montable en el slim sin cargar el módulo `session.py` del full. No cambia el comportamiento funcional del router en el full.

### D5 — SlimSettings: nuevos campos con defaults seguros

**Decisión**: Agregar a `SlimSettings`:
```python
auth_provider: str = "jwt"
jwt_own_secret: str  # obligatorio — sin default; Railway lo inyecta
jwt_own_issuer: str = "activeexam-auth"
jwt_audience: str = "activeexam"
access_token_ttl_seconds: int = 900
refresh_token_ttl_seconds: int = 604800
embedding_encryption_key: str  # obligatorio — sin default
```

`jwt_own_secret` y `embedding_encryption_key` son obligatorios (sin default): si Railway no los inyecta, el proceso falla al arrancar con error explícito (twelve-factor, sin secreto hardcodeado).

### D6 — db_photo_storage.py: adaptador foto→DB como callable compatible con ProfilePhotoStorageService

**Decisión**: Crear `backend/app/infrastructure/storage/db_photo_storage.py` con un adaptador que implemente la misma interfaz que `ProfilePhotoStorageService` (o bien, dado que `put_fn` es un callable inyectable, crear un `put_fn` que escriba en DB a través de la session). En el slim, la "subida" de la foto escribe `foto_bytes` en la tabla `foto_referencia` directamente.

**Trade-off**: `GuardarFotoPerfilService` en el full espera un `put_fn(bucket, key, data) -> None` y luego persiste el `uri_storage`. En el slim, el uri_storage no aplica. Opciones: (a) crear un servicio slim paralelo `GuardarFotoPerfilSlimService` que persista directamente en BYTEA, o (b) adaptar el existente pasando un `put_fn` que escriba en DB y devuelva el key como ID. Se elige (a) — evita contaminar el servicio del full con lógica del slim.

## Risks / Trade-offs

- **[Risk] BYTEA en DB para fotos**: fotos grandes (>1 MB) pueden inflar el tamaño de Postgres y ralentizar backups. → Mitigation: validar tamaño máximo de foto en el router (rechazar si >500 KB base64 decoded). Para escala, migrar a S3 en un change futuro.
- **[Risk] schema divergente de foto_referencia entre full y slim**: si en el futuro se quiere unificar, hay que hacer una migración de datos compleja. → Mitigation: documentar la divergencia explícitamente en el código y en el design. Aceptable para MVP.
- **[Risk] JwtValidator con jwks_cache=None**: si por alguna razón el código del JwtValidator hace un call al cache (ej. en algún path de RS256), falla con AttributeError. → Mitigation: verificar en slim_wiring que el JwtValidator nunca intente resolver RS256 cuando jwks_cache=None. Usar un JwksCache stub (cache vacío que siempre lanza NotImplementedError para RS256) si el validator lo requiere.
- **[Risk] tabla usuario duplicada en la historia de Alembic**: puede confundir a futuros desarrolladores. → Mitigation: comentario explícito en la migración 0008 explicando el diseño.
- **[Risk] enrollment/router.py modificado afecta el full**: el router es compartido. Cualquier cambio debe ser retrocompatible. → Mitigation: el cambio es solo la fuente de la `session_factory` — el full cableba `app.state.session_factory` en `create_app()`, igual que el slim.

## Migration Plan

1. Crear `0008_c57_auth_biometria_slim.py` (down_revision=0005, sin depends_on).
2. Crear `slim_wiring.py` y `db_photo_storage.py`.
3. Extender `SlimSettings` con los campos nuevos.
4. Ajustar `enrollment/router.py` (cambio mínimo — import de session_factory).
5. Extender `main_slim.py`: lifespan + routers.
6. Verificar `seed_users.py` contra tablas del slim.
7. Tests de integración contra `postgres:16-alpine` (SIN timescale).
8. Documentar env vars en README de deploy / Railway dashboard.

**Rollback**: si la 0008 falla en Railway, `alembic downgrade slim@0005` revierte a solo proctoring. Los routers auth/users/enrollment no estarán montados si falla el lifespan, pero el proceso fallará al arrancar (mejor que silenciosamente).

## Open Questions

1. **¿El `JwtValidator` actual maneja `jwks_cache=None` sin crash?** — Verificar en `jwt_validator.py` antes de implementar slim_wiring. Si no, inyectar un cache stub.
2. **¿`GuardarFotoPerfilService` permite sustituir la lógica de persistencia completa, o hace asunciones sobre el formato de `uri_storage`?** — Si asume uri_storage no-nulo, crear `GuardarFotoPerfilSlimService` es obligatorio.
3. **¿El seed `seed_users.py` importa `get_settings()` del full?** — Si sí, requiere un argumento `--slim` o una variante que use `SlimSettings`.
4. **env var `PORT` en Railway**: ya soportada en SlimSettings. Confirmar que el Dockerfile.slim usa `${PORT:-8000}` en el CMD.
