## ADDED Requirements

### Requirement: migración 0008 pertenece a la rama slim y no depende de la rama principal

La migración `0008_c57_auth_biometria_slim.py` SHALL tener `down_revision="0005"`, `branch_labels=None`, `depends_on=None`. No SHALL referenciar ninguna migración de la rama principal (0001–0007). Esto garantiza que `alembic upgrade slim@head` aplique 0005 → 0008 sin ejecutar `CREATE EXTENSION timescaledb`.

#### Scenario: slim@head en Postgres sin timescaledb aplica solo 0005 y 0008
- **WHEN** se ejecuta `alembic upgrade slim@head` contra postgres:16-alpine desde cero
- **THEN** se aplican exactamente las revisiones 0005 y 0008 (verificable con `alembic history`) sin error

#### Scenario: downgrade de 0008 revierte exactamente las 4 tablas
- **WHEN** se ejecuta `alembic downgrade slim@0005`
- **THEN** las tablas `usuario`, `refresh_tokens`, `foto_referencia` y `embedding_referencia` son eliminadas y las tablas de proctoring (creadas por 0005) permanecen intactas

### Requirement: migración 0008 crea tabla refresh_tokens en la rama slim

La migración SHALL crear `refresh_tokens` con columnas `id UUID PK`, `jti TEXT NOT NULL UNIQUE`, `usuario_id UUID FK→usuario.id CASCADE DELETE`, `expires_at TIMESTAMPTZ NOT NULL`, `rotado_en TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Con índices en `jti` (unique), `usuario_id` y `expires_at`.

#### Scenario: refresh_tokens FK a usuario CASCADE DELETE funciona
- **WHEN** se elimina un usuario de la tabla `usuario`
- **THEN** todos sus `refresh_tokens` son eliminados automáticamente por CASCADE

### Requirement: la migración 0008 es idempotente (no-destructiva, paso 1 de 2)

La migración SHALL crear solo tablas nuevas (no modificar columnas existentes en otras tablas). Es deployable sin downtime (no requiere bloqueos de tabla sobre datos existentes).

#### Scenario: 0008 upgrade no modifica proctoring_session ni proctoring_event
- **WHEN** se ejecuta el upgrade de 0008 con datos existentes en proctoring_session
- **THEN** los datos existentes permanecen intactos y las consultas a proctoring siguen funcionando
