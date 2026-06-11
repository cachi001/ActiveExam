## MODIFIED Requirements

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL verificar que el alumno tenga un registro `embedding_referencia` con `vigente = TRUE` en la base de datos (además de consentimiento válido) como condición para que `puedeRendir()` retorne `{ puede: true }`. La verificación SHALL ser server-side: el backend evaluará si existe la referencia biométrica persistida, no si existe en el store del cliente.

#### Scenario: Gate permite rendir con perfil completo incluyendo referencia biométrica persistida
- **WHEN** el alumno tiene consentimiento válido Y tiene un registro `embedding_referencia` con `vigente = TRUE` en la DB
- **THEN** `api.puedeRendir()` (que llama al backend) retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate bloquea el examen si falta referencia biométrica en backend
- **WHEN** el alumno tiene consentimiento válido PERO no tiene un registro `embedding_referencia` con `vigente = TRUE` en la DB
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra un mensaje con la razón del bloqueo y un enlace a `/alumno/perfil` para completar el enrollment biométrico

#### Scenario: Gate bloquea si la referencia existe en localStorage pero no en backend
- **WHEN** el store Zustand o localStorage contiene un `referencia_id` pero el backend no tiene un registro `vigente = TRUE` para ese `usuario_id`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** la verificación es server-side y no puede ser bypasseada por manipulación del store local

## ADDED Requirements

### Requirement: La fase biometria del enrollment devuelve un referencia_id opaco al cliente
El sistema SHALL garantizar que al completar la fase `biometria` del enrollment, el cliente recibe únicamente el `referencia_id` (UUID opaco) del embedding persistido en el backend. El embedding crudo (array de floats) SHALL ser descartado del estado del cliente tras la confirmación del backend. El cliente SHALL tratar el `referencia_id` como un identificador de referencia para uso futuro (e.g., indicar qué referencia usar en la verificación de C-09), no como un dato biométrico.

#### Scenario: referencia_id almacenado en store tras enrollment exitoso
- **WHEN** `POST /api/v1/enrollment/embedding-referencia` retorna `{ referencia_id: "<uuid>" }` con HTTP 201
- **THEN** el store Zustand persiste `{ biometrico_referencia_id: "<uuid>" }` (u equivalente)
- **THEN** el embedding crudo es descartado de la memoria del cliente y de localStorage

#### Scenario: referencia_id visible como metadato en el perfil del alumno (UI)
- **WHEN** el alumno navega a `/alumno/perfil` y la sección de biometría está completada
- **THEN** la UI muestra el estado `completado` para la sección biométrica
- **THEN** la UI NO muestra el embedding crudo (ni parcialmente); puede mostrar el `referencia_id` truncado como referencia visual si el diseño lo requiere
