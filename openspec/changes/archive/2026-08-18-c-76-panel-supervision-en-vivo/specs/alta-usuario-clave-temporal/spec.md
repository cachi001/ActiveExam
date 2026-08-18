## ADDED Requirements

### Requirement: Página dedicada de alta de usuario
El sistema SHALL ofrecer una **página dedicada** (ruta estilo `/admin/usuarios/nuevo`) con un formulario de alta de usuario, accesible únicamente por quien tiene la capacidad `gestionar_usuarios` (`admin_sistema`). El alta SHALL invocar el endpoint existente `POST /users`, sin cambiar su contrato.

#### Scenario: Admin abre la página de alta
- **WHEN** un usuario con capacidad `gestionar_usuarios` navega a `/admin/usuarios/nuevo`
- **THEN** ve el formulario dedicado de alta de usuario

#### Scenario: Usuario sin permiso no accede
- **WHEN** un usuario sin capacidad `gestionar_usuarios` intenta abrir la página de alta
- **THEN** el acceso es rechazado

### Requirement: Modal post-creación con la clave temporal
Cuando el alta se realiza sin contraseña provista por el admin y el backend devuelve `password_generada`, el sistema SHALL mostrar un **modal** (no un toast efímero) que presente la clave temporal de forma legible, con un botón **copiar** (portapapeles), y los avisos: "guardala, no la vas a volver a ver" y "el usuario deberá cambiarla en el primer ingreso". La clave temporal NO SHALL persistirse en estado global ni en logs del cliente.

#### Scenario: Modal muestra la clave con botón copiar
- **WHEN** el alta devuelve `password_generada`
- **THEN** se abre un modal con la clave visible, un botón que la copia al portapapeles, y los avisos de un solo uso y cambio obligatorio

#### Scenario: Sin clave generada no hay modal de clave
- **WHEN** el admin provee una contraseña en el alta y el backend NO devuelve `password_generada`
- **THEN** no se muestra el modal de clave temporal; el alta se confirma normalmente

#### Scenario: La clave no queda en un toast efímero
- **WHEN** se crea un usuario con clave generada
- **THEN** la clave se muestra en el modal persistente y NO en un toast que desaparece solo
