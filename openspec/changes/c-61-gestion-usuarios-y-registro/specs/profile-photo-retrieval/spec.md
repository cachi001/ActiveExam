## ADDED Requirements

### Requirement: Lectura de la foto de perfil propia

El sistema SHALL exponer `GET /api/v1/enrollment/foto-perfil` que devuelve la foto de perfil vigente del usuario autenticado. La respuesta MUST entregar la imagen como base64 dataURL en JSON. El binario MUST NOT loguearse. Si el usuario no tiene foto vigente, el sistema MUST responder 404.

#### Scenario: Usuario obtiene su foto

- **WHEN** un usuario autenticado con foto vigente hace `GET /api/v1/enrollment/foto-perfil`
- **THEN** el sistema responde 200 con la imagen en base64

#### Scenario: Sin foto vigente

- **WHEN** un usuario autenticado sin foto vigente hace `GET /api/v1/enrollment/foto-perfil`
- **THEN** el sistema responde 404

#### Scenario: Sin token

- **WHEN** se hace `GET /api/v1/enrollment/foto-perfil` sin Bearer token
- **THEN** el sistema responde 401

### Requirement: Lectura de la foto de perfil de otro usuario por rol autorizado

El sistema SHALL exponer `GET /api/v1/enrollment/foto-perfil/{usuario_id}` que permite a un `admin_sistema` o `proctor` autorizado obtener la foto de perfil de otro usuario. El acceso a la foto de un tercero (dato sensible, Ley 25.326) MUST restringirse por rol y MUST NOT estar disponible para el rol `estudiante` sobre fotos ajenas. El binario MUST NOT loguearse.

#### Scenario: Admin obtiene la foto de un usuario

- **WHEN** un `admin_sistema` hace `GET /api/v1/enrollment/foto-perfil/{usuario_id}` de un usuario con foto vigente
- **THEN** el sistema responde 200 con la imagen en base64

#### Scenario: Estudiante no puede ver foto ajena

- **WHEN** un `estudiante` hace `GET /api/v1/enrollment/foto-perfil/{otro_usuario_id}`
- **THEN** el sistema responde 403

#### Scenario: Usuario objetivo sin foto

- **WHEN** un rol autorizado pide la foto de un usuario sin foto vigente
- **THEN** el sistema responde 404

### Requirement: Render del avatar en el frontend

El frontend SHALL exponer `api.obtenerFotoPerfil()` (y la variante por `usuario_id` para staff) y mostrar la foto como avatar donde corresponda (header de perfil del alumno y tabla de gestión de usuarios), con fallback cuando no hay foto.

#### Scenario: Avatar visible en el perfil

- **WHEN** el alumno tiene una foto de perfil guardada y entra a su perfil
- **THEN** la foto se muestra como avatar

#### Scenario: Fallback sin foto

- **WHEN** el usuario no tiene foto de perfil
- **THEN** la UI muestra un avatar de fallback sin romper el layout
