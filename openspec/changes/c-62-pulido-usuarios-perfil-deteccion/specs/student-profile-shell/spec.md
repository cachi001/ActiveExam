## MODIFIED Requirements

### Requirement: La pantalla de perfil muestra los datos personales del alumno
El sistema SHALL proveer la pantalla `/alumno/perfil` que muestre el nombre completo (nombre y apellido), legajo, email institucional y la institución del alumno autenticado.

#### Scenario: Datos personales visibles en el perfil
- **WHEN** el alumno navega a `/alumno/perfil`
- **THEN** se muestran: nombre completo (nombre + apellido), legajo (`id_institucional`), email institucional e institución

#### Scenario: Título del header muestra nombre y apellido
- **WHEN** el alumno autenticado tiene nombre "Juan" y apellido "García"
- **THEN** el encabezado `PerfilHeaderCard` SHALL mostrar el texto "Juan García" como título principal
- **WHEN** el alumno tiene nombre pero no apellido (apellido ausente o null)
- **THEN** el encabezado SHALL mostrar solo el nombre disponible sin espacio ni guión adicional

#### Scenario: Email del perfil es de UTN FRM
- **WHEN** el alumno autenticado es el principal de demo para rol `estudiante`
- **THEN** el email mostrado en el perfil termina en `@frm.utn.edu.ar`

## ADDED Requirements

### Requirement: El tipo Principal incluye apellido
El tipo frontend `Principal` (en `frontend/src/lib/types.ts`) SHALL declarar el campo `apellido?: string`. El campo es opcional para mantener compatibilidad con tokens que no lo provean.

#### Scenario: Principal con apellido desde /auth/me
- **WHEN** el frontend llama a `GET /auth/me` y el usuario tiene apellido en la DB
- **THEN** la respuesta SHALL incluir el campo `apellido` con el valor almacenado
- **THEN** el store del frontend SHALL persistir `apellido` en el objeto `Principal`

#### Scenario: Principal sin apellido no rompe la UI
- **WHEN** el campo `apellido` es `null` o `undefined` en el principal
- **THEN** el frontend SHALL renderizar solo el nombre sin crash ni artefacto visual

### Requirement: GET /auth/me devuelve nombre y apellido desde la DB
El endpoint `GET /auth/me` SHALL incluir los campos `nombre` (str | None) y `apellido` (str | None) en la respuesta `PrincipalResponse`, obteniéndolos mediante una query a `UsuarioModel` por `UsuarioModel.id = principal.subject`.

#### Scenario: nombre y apellido presentes cuando el usuario los tiene
- **WHEN** un usuario autenticado tiene `nombre = "Ana"` y `apellido = "López"` en la DB
- **THEN** `GET /auth/me` SHALL devolver `{"nombre": "Ana", "apellido": "López", ...}`

#### Scenario: nombre y apellido null cuando el usuario no los tiene
- **WHEN** un usuario autenticado tiene `nombre = null` y `apellido = null` en la DB
- **THEN** `GET /auth/me` SHALL devolver `{"nombre": null, "apellido": null, ...}` sin error 500

#### Scenario: degradación graceful si la DB no está disponible
- **WHEN** `session_factory` no está disponible en `app.state`
- **THEN** `GET /auth/me` SHALL devolver `{"nombre": null, "apellido": null, ...}` (sin falla del endpoint)
- **THEN** los demás campos del principal (id_institucional, email, roles, mfa_satisfecho) SHALL seguir presentes y correctos
