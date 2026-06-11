## ADDED Requirements

### Requirement: Auto-registro público de estudiantes

El sistema SHALL exponer `POST /api/v1/auth/register` como endpoint PÚBLICO (sin autenticación) que permite a un estudiante auto-registrarse con sus datos personales. El endpoint MUST forzar el rol a `["estudiante"]` server-side y MUST NOT aceptar un campo `roles` en el body. El schema MUST usar `extra='forbid'`. El password MUST hashearse con bcrypt antes de persistir y el `auth_provider` MUST quedar en `"local"`.

#### Scenario: Registro exitoso

- **WHEN** un visitante hace `POST /api/v1/auth/register` con nombre, apellido, id_institucional, email institucional válido, password y password_confirmacion coincidentes
- **THEN** el sistema crea el usuario con rol `estudiante`, auth_provider `local`, y responde 201

#### Scenario: No se puede auto-asignar rol elevado

- **WHEN** el body incluye un campo `roles` (ej. `["admin_sistema"]`)
- **THEN** el sistema responde 422 por `extra='forbid'` y no crea ningún usuario

#### Scenario: Email fuera del dominio institucional

- **WHEN** el email no pertenece al dominio institucional configurado
- **THEN** el sistema responde 422 y no crea el usuario

#### Scenario: Password no coincide o débil

- **WHEN** `password` y `password_confirmacion` difieren, o el password no cumple la fuerza mínima
- **THEN** el sistema responde 422

#### Scenario: Email o id_institucional duplicado

- **WHEN** ya existe un usuario con el mismo email o id_institucional
- **THEN** el sistema responde 409

#### Scenario: El password no se persiste en claro

- **WHEN** se registra un usuario
- **THEN** la columna `password_hash` contiene un hash bcrypt y el password en claro nunca se almacena ni se loguea

### Requirement: Datos personales del usuario

El modelo `usuario` SHALL incluir las columnas `nombre` y `apellido` (nullable, para compatibilidad con usuarios preexistentes). Estas columnas SHALL persistirse en el auto-registro y poder mostrarse en la UI. La migración que las agrega MUST vivir en la rama Alembic del slim (`down_revision = "0008"`, `depends_on = None`) sin introducir dependencias de TimescaleDB.

#### Scenario: Persistencia de nombre y apellido

- **WHEN** un estudiante se registra con nombre y apellido
- **THEN** ambos quedan persistidos y se devuelven en las respuestas de usuario que los incluyan

#### Scenario: Compatibilidad con usuarios sin nombre

- **WHEN** existe un usuario previo sin nombre/apellido
- **THEN** las consultas y la UI lo manejan con fallback (email o id_institucional) sin error

### Requirement: Pantalla de registro en el frontend

El frontend SHALL ofrecer una pantalla de registro (signup) enlazada desde el login, que reúse el componente de input reusable definido por C-60. La pantalla MUST validar en cliente el dominio de email institucional y la coincidencia de password antes de enviar, y tras un registro exitoso MUST dirigir al usuario al login.

#### Scenario: Acceso al registro desde el login

- **WHEN** un visitante está en la pantalla de login
- **THEN** ve un enlace para registrarse que lleva a la pantalla de signup

#### Scenario: Registro exitoso redirige al login

- **WHEN** el usuario completa el registro correctamente
- **THEN** la UI lo lleva a la pantalla de login para iniciar sesión
