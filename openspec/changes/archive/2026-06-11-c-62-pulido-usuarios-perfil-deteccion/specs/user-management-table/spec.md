## ADDED Requirements

### Requirement: La lista de usuarios usa tabla en desktop y cards en mobile
En pantallas `md+` el sistema SHALL renderizar la lista de usuarios como una tabla HTML semántica (`<table>`) con columnas: Avatar+Nombre, Email, Legajo, Roles, Acciones. En pantallas menores a `md` el sistema SHALL renderizar cards individuales con fondo blanco, borde sutil (`border-outline-variant`) y sombra suave.

#### Scenario: Vista tabla en desktop
- **WHEN** el administrador accede a `/admin/usuarios` en una pantalla de ancho >= 768px
- **THEN** la lista de usuarios SHALL mostrarse como una tabla con columnas Avatar+Nombre, Email, Legajo, Roles, Acciones
- **THEN** la tabla SHALL tener encabezados de columna visibles y el cuerpo con una fila por usuario

#### Scenario: Vista cards en mobile
- **WHEN** el administrador accede a `/admin/usuarios` en una pantalla de ancho < 768px
- **THEN** la lista de usuarios SHALL mostrarse como cards individuales
- **THEN** cada card SHALL tener fondo blanco, borde sutil y sombra suave

#### Scenario: Avatar en tabla
- **WHEN** un usuario tiene foto de perfil cargada
- **THEN** la celda Avatar+Nombre SHALL mostrar la foto circular junto al nombre completo
- **WHEN** un usuario no tiene foto de perfil
- **THEN** la celda Avatar+Nombre SHALL mostrar un avatar con la inicial del nombre

### Requirement: El campo auth_provider no se muestra en la lista de usuarios
El campo `auth_provider` (valor "jwt" o "local") SHALL NOT aparecer en ninguna vista de la lista de usuarios (ni tabla ni cards). El campo permanece en el tipo `UsuarioAdmin` y en el backend pero es un detalle de infraestructura invisible al administrador.

#### Scenario: auth_provider ausente en tabla
- **WHEN** el administrador ve la tabla de usuarios en desktop
- **THEN** ninguna columna ni celda SHALL mostrar el valor del campo `auth_provider`

#### Scenario: auth_provider ausente en cards
- **WHEN** el administrador ve las cards de usuarios en mobile
- **THEN** ninguna card SHALL mostrar el valor del campo `auth_provider`

### Requirement: Los roles se muestran con labels normalizados en la lista
La lista de usuarios (tabla y cards) SHALL mostrar los nombres de roles en español usando `ROL_LABELS`: `estudiante` → "Estudiante", `proctor` → "Proctor", `admin_sistema` → "Administrador del sistema". No se muestran los identificadores en snake_case crudos.

#### Scenario: Labels normalizados en tabla
- **WHEN** un usuario tiene roles `["estudiante", "admin_sistema"]`
- **THEN** la columna Roles de la tabla SHALL mostrar "Estudiante, Administrador del sistema"

#### Scenario: Labels normalizados en cards
- **WHEN** un usuario tiene rol `["proctor"]`
- **THEN** la card SHALL mostrar "Proctor" en el campo de roles

### Requirement: El formulario create/edit usa checkboxes para seleccionar roles
El formulario de creación y edición de usuarios SHALL reemplazar el campo de texto libre "Roles (separados por coma)" por tres checkboxes independientes, uno por rol disponible: Estudiante, Proctor, Administrador del sistema. Al menos un rol SHALL estar seleccionado para poder guardar.

#### Scenario: Checkboxes visibles en formulario de creación
- **WHEN** el administrador abre el formulario de creación de usuario
- **THEN** SHALL aparecer tres checkboxes: "Estudiante", "Proctor", "Administrador del sistema"
- **THEN** ningún checkbox SHALL estar marcado por defecto

#### Scenario: Checkboxes pre-seleccionados al editar
- **WHEN** el administrador abre el formulario de edición de un usuario con roles `["proctor"]`
- **THEN** el checkbox "Proctor" SHALL estar marcado
- **THEN** los checkboxes "Estudiante" y "Administrador del sistema" SHALL estar desmarcados

#### Scenario: Error al guardar sin roles
- **WHEN** el administrador intenta guardar el formulario sin ningún checkbox seleccionado
- **THEN** el sistema SHALL mostrar el mensaje de error "Ingresá al menos un rol válido." sin enviar la petición al backend
