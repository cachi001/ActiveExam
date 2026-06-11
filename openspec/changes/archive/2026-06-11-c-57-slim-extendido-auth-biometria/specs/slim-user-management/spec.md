## ADDED Requirements

### Requirement: main_slim monta users_router

`main_slim.py` SHALL montar el router de usuarios (`presentation/api/v1/users/router.py`) en `/api/v1/users`. El router existente no se modifica.

#### Scenario: POST /api/v1/users/ por admin_sistema crea un usuario
- **WHEN** un usuario con rol `admin_sistema` hace `POST /api/v1/users/` con `id_institucional`, `email`, `password` (>=8 chars) y `roles` válidos
- **THEN** la respuesta es 201 con el UUID del usuario creado y el password hasheado con bcrypt en la tabla `usuario`

#### Scenario: POST /api/v1/users/ por no-admin es rechazado
- **WHEN** un usuario con rol `estudiante` o `proctor` hace `POST /api/v1/users/`
- **THEN** la respuesta es 403

#### Scenario: usuario duplicado es rechazado
- **WHEN** se intenta crear un usuario con `email` o `id_institucional` ya existente en la tabla `usuario`
- **THEN** la respuesta es 409

### Requirement: tabla usuario existe en la rama slim

La migración `0008` SHALL crear la tabla `usuario` en la rama slim con columnas: `id UUID PK`, `id_institucional VARCHAR(255) UNIQUE NOT NULL`, `email VARCHAR(320) NOT NULL`, `roles JSONB NOT NULL DEFAULT '[]'`, `attrs_federados JSONB NOT NULL DEFAULT '{}'`, `password_hash TEXT NULL`, `auth_provider TEXT NOT NULL DEFAULT 'jwt'`. Sin `depends_on` de la rama principal.

#### Scenario: alembic upgrade slim@head en Postgres estándar crea tabla usuario
- **WHEN** se ejecuta `alembic upgrade slim@head` contra `postgres:16-alpine` (sin TimescaleDB)
- **THEN** la tabla `usuario` existe con todas las columnas correctas y sin error de extensión

### Requirement: seed_users.py funciona contra el slim

El script `backend/scripts/seed_users.py` SHALL funcionar con las tablas creadas por la migración 0008 (rama slim), sin requerir tablas de la rama principal.

#### Scenario: seed crea los 3 usuarios de rol base
- **WHEN** se ejecuta `seed_users.py` con `DATABASE_URL` apuntando al slim (sin TimescaleDB)
- **THEN** se crean al menos 3 usuarios (estudiante, proctor, admin_sistema) con passwords hasheados y `auth_provider='jwt'`
