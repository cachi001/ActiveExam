# user-local-auth Specification

## Purpose
TBD - created by archiving change c-55-auth-provider-jwt-propio. Update Purpose after archive.
## Requirements
### Requirement: Endpoint POST /api/v1/auth/login
El sistema SHALL exponer `POST /api/v1/auth/login` (ruta pública) que recibe `email_o_username` (string) y `password` (string), verifica el hash bcrypt contra `UsuarioModel.password_hash`, y responde con `access_token` (JWT propio), `refresh_token`, `token_type: "Bearer"` y `expires_in`. El schema SHALL usar `model_config = ConfigDict(extra='forbid')`. La ruta SHALL ser pública (sin Bearer requerido).

#### Scenario: Login exitoso con email
- **WHEN** `POST /api/v1/auth/login` recibe email y password correctos de un usuario con `password_hash` registrado
- **THEN** responde 200 con `access_token` JWT válido, `refresh_token` persistido en DB, y `expires_in` en segundos

#### Scenario: Login exitoso con username (id_institucional)
- **WHEN** `POST /api/v1/auth/login` recibe `id_institucional` y password correctos
- **THEN** responde 200 con tokens válidos (busca por email O id_institucional)

#### Scenario: Password incorrecto rechazado
- **WHEN** `POST /api/v1/auth/login` recibe credenciales con password incorrecto
- **THEN** responde 401 con mensaje genérico (no indica si el usuario existe o no — prevención de enumeración)

#### Scenario: Usuario sin password_hash (federado Keycloak)
- **WHEN** `POST /api/v1/auth/login` recibe credenciales de un usuario con `password_hash IS NULL`
- **THEN** responde 401 con mensaje genérico (no expone que el usuario existe con otro provider)

#### Scenario: Usuario inexistente
- **WHEN** `POST /api/v1/auth/login` recibe email/username que no existe en DB
- **THEN** responde 401 con el mismo mensaje genérico (tiempo de respuesta constante — defensa timing)

### Requirement: Campo password_hash en UsuarioModel — migración en dos pasos
El sistema SHALL agregar el campo `password_hash TEXT` (nullable) y `auth_provider TEXT DEFAULT 'keycloak'` a `UsuarioModel` mediante migración Alembic en dos pasos: (1) ADD COLUMN nullable + crear tabla `refresh_tokens`; (2) no se agrega NOT NULL porque usuarios federados legítimamente no tienen password local.

#### Scenario: Usuario Keycloak existente no afectado por la migración
- **WHEN** se aplica la migración paso 1
- **THEN** los usuarios existentes tienen `password_hash = NULL` y `auth_provider = 'keycloak'`, y el login Keycloak sigue funcionando sin cambio

#### Scenario: Usuario con password_hash tiene auth_provider = 'local'
- **WHEN** se crea un usuario con password via el endpoint de creación
- **THEN** `auth_provider = 'local'` y `password_hash` contiene el hash bcrypt del password

### Requirement: Hashing de passwords con bcrypt (12 rounds)
El sistema SHALL usar `passlib[bcrypt]` con `rounds=12` para hashear passwords. El hash SHALL verificarse en tiempo constante (passlib lo garantiza). Las passwords NUNCA SHALL ser logueadas ni expuestas en respuestas de error o traces de observabilidad.

#### Scenario: Hash generado correctamente en creación
- **WHEN** se crea un usuario con password via el endpoint protegido
- **THEN** `UsuarioModel.password_hash` contiene un hash bcrypt válido (prefijo `$2b$12$`)

#### Scenario: Verificación en tiempo constante
- **WHEN** `POST /api/v1/auth/login` recibe un password incorrecto para un usuario existente
- **THEN** el tiempo de respuesta es estadísticamente similar al de un password correcto (passlib.verify siempre corre el hash completo)

### Requirement: Endpoint protegido de creación de usuario con password
El sistema SHALL exponer `POST /api/v1/users/` (requiere rol `admin_sistema`) para crear usuarios con password local. El request SHALL incluir `email`, `id_institucional`, `password`, `roles[]`. El sistema SHALL rechazar passwords < 8 caracteres. El sistema SHALL rechazar la creación si `email` o `id_institucional` ya existen (409 Conflict). El schema SHALL usar `model_config = ConfigDict(extra='forbid')`.

#### Scenario: Creación exitosa por admin_sistema
- **WHEN** `POST /api/v1/users/` recibe datos válidos con un Bearer de rol `admin_sistema`
- **THEN** crea el usuario en DB con `password_hash` bcrypt y `auth_provider = 'local'`, responde 201 con el usuario creado (sin `password_hash` en la respuesta)

#### Scenario: Sin rol admin_sistema rechazado con 403
- **WHEN** `POST /api/v1/users/` recibe un Bearer de rol `estudiante` o `proctor`
- **THEN** responde 403 Forbidden

#### Scenario: Email duplicado rechazado con 409
- **WHEN** `POST /api/v1/users/` intenta crear un usuario con email ya existente
- **THEN** responde 409 Conflict sin crear el usuario

### Requirement: Seed de usuarios de prueba para entornos no-producción
El sistema SHALL proveer un script `backend/scripts/seed_users.py` que crea 3 usuarios demo (roles: `estudiante`, `proctor`, `admin_sistema`) con passwords desde variables de entorno (`SEED_ESTUDIANTE_PASSWORD`, `SEED_PROCTOR_PASSWORD`, `SEED_ADMIN_PASSWORD`). El script SHALL fallar explícitamente si se ejecuta con `environment=production`. El script SHALL ser idempotente (no duplica si el usuario ya existe).

#### Scenario: Seed crea usuarios idempotentemente
- **WHEN** el script seed se ejecuta dos veces en entorno local con las mismas variables
- **THEN** no hay duplicados — la segunda ejecución detecta los usuarios existentes y los omite

#### Scenario: Seed bloqueado en producción
- **WHEN** el script seed se ejecuta con `ENVIRONMENT=production`
- **THEN** falla con error explícito antes de tocar la DB

