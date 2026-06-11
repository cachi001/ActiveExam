## ADDED Requirements

### Requirement: Listado paginado de usuarios

El sistema SHALL exponer `GET /api/v1/users/` que devuelve la lista de usuarios paginada, accesible SÓLO para el rol `admin_sistema`. La respuesta MUST excluir por defecto los usuarios dados de baja (`eliminado_en IS NOT NULL`) y MUST NOT incluir el `password_hash` en el payload.

#### Scenario: Admin lista usuarios

- **WHEN** un `admin_sistema` autenticado hace `GET /api/v1/users/?limit=20&offset=0`
- **THEN** el sistema responde 200 con un array de usuarios (id, id_institucional, email, nombre, apellido, roles, auth_provider) y metadatos de paginación, sin password_hash

#### Scenario: Rol insuficiente

- **WHEN** un usuario con rol `estudiante` o `proctor` hace `GET /api/v1/users/`
- **THEN** el sistema responde 403

#### Scenario: Sin token

- **WHEN** se hace `GET /api/v1/users/` sin Bearer token
- **THEN** el sistema responde 401

#### Scenario: Usuarios dados de baja excluidos

- **WHEN** un `admin_sistema` lista usuarios y existe al menos uno con `eliminado_en` no nulo
- **THEN** ese usuario NO aparece en la respuesta por defecto

### Requirement: Edición de email y roles

El sistema SHALL exponer `PUT /api/v1/users/{usuario_id}` que permite a un `admin_sistema` modificar el `email` y los `roles` de un usuario. Los roles MUST validarse contra el conjunto de roles válidos (`estudiante`, `proctor`, `admin_sistema`). El endpoint MUST NOT permitir modificar `password_hash` ni `auth_provider`. El schema MUST usar `extra='forbid'`.

#### Scenario: Edición exitosa

- **WHEN** un `admin_sistema` hace `PUT /api/v1/users/{id}` con `{ "email": "nuevo@frm.utn.edu.ar", "roles": ["proctor"] }`
- **THEN** el sistema responde 200 con el usuario actualizado

#### Scenario: Rol inválido

- **WHEN** un `admin_sistema` envía un rol que no pertenece al conjunto válido
- **THEN** el sistema responde 422

#### Scenario: Admin no puede quitarse su propio rol admin

- **WHEN** un `admin_sistema` hace `PUT` sobre su propio usuario removiendo `admin_sistema` de sus roles
- **THEN** el sistema rechaza la operación (4xx) para evitar lockout

#### Scenario: Campo no declarado

- **WHEN** el body incluye un campo fuera del schema (ej. `password_hash`)
- **THEN** el sistema responde 422 por `extra='forbid'`

#### Scenario: Usuario inexistente

- **WHEN** un `admin_sistema` hace `PUT` sobre un `usuario_id` que no existe
- **THEN** el sistema responde 404

### Requirement: Baja de usuario (soft-delete)

El sistema SHALL exponer `DELETE /api/v1/users/{usuario_id}` que da de baja a un usuario mediante soft-delete (setea `eliminado_en = now()`), accesible SÓLO para `admin_sistema`. La baja MUST NOT eliminar físicamente la fila ni la evidencia asociada (cadena de custodia). La baja MUST revocar los refresh tokens vigentes del usuario y el usuario dado de baja MUST NOT poder autenticarse.

#### Scenario: Baja exitosa

- **WHEN** un `admin_sistema` hace `DELETE /api/v1/users/{id}` de un usuario activo
- **THEN** el sistema responde 204, el usuario queda con `eliminado_en` no nulo y deja de aparecer en el listado

#### Scenario: Usuario dado de baja no puede loguear

- **WHEN** un usuario con `eliminado_en` no nulo intenta `POST /api/v1/auth/login` con credenciales válidas
- **THEN** el sistema responde 401 con el mensaje genérico de credenciales inválidas

#### Scenario: La evidencia no se destruye

- **WHEN** se da de baja a un usuario con sesiones o casos disciplinarios asociados
- **THEN** la evidencia con cadena de custodia permanece intacta en la base

#### Scenario: Rol insuficiente para baja

- **WHEN** un usuario sin rol `admin_sistema` hace `DELETE /api/v1/users/{id}`
- **THEN** el sistema responde 403

### Requirement: UI administrativa de gestión de usuarios

El frontend SHALL ofrecer una pantalla de gestión de usuarios para el `admin_sistema`, integrada a la navegación de staff (`STAFF_NAV`), que permita listar (responsive), crear, editar y dar de baja usuarios con confirmación. Los formularios MUST reutilizar el componente de input reusable definido por C-60. Los avatares en la tabla MUST usar el endpoint de lectura de foto de perfil cuando exista.

#### Scenario: Acceso desde el panel admin

- **WHEN** un `admin_sistema` navega a la sección de gestión de usuarios
- **THEN** ve la lista de usuarios con acciones de crear, editar y dar de baja

#### Scenario: Baja con confirmación

- **WHEN** el admin pulsa dar de baja a un usuario
- **THEN** la UI pide confirmación explícita antes de invocar el `DELETE`
