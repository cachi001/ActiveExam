## ADDED Requirements

### Requirement: El estado de sesión seguro sobrevive a una recarga

El cliente MUST persistir a través de una recarga el estado de sesión no sensible
(rol y preferencias de UI) para que el usuario no pierda su contexto ni vea un
parpadeo de "no autenticado". El principal se restaura desde la fuente de verdad
de autenticación (token), no desde una copia duplicada.

#### Scenario: Recargar mantiene el rol y el contexto de UI
- **WHEN** un usuario autenticado recarga la página (F5)
- **THEN** su rol y preferencias de UI se rehidratan desde el almacenamiento del cliente
- **AND** no se muestra un estado transitorio de "no autenticado" ni se pierde la ruta

#### Scenario: El principal tiene una única fuente de verdad
- **WHEN** una pantalla necesita el principal (nombre, email, rol)
- **THEN** lo obtiene de la fuente de autenticación única
- **AND** no existen dos copias del principal que puedan divergir

### Requirement: La biometría NUNCA se persiste en el cliente

El allowlist de persistencia MUST excluir cualquier dato biométrico (embedding,
descriptor facial) y cualquier token de autenticación. Solo el `referencia_id`
opaco puede vivir en el cliente (Ley 25.326, regla dura del proyecto).

#### Scenario: El estado persistido no contiene biometría ni tokens
- **WHEN** se serializa el estado del cliente al almacenamiento
- **THEN** el contenido persistido no incluye embeddings, descriptores faciales ni el token
- **AND** solo incluye el allowlist explícito (rol, preferencias de UI, ids opacos)

### Requirement: El estado persistido incompatible se descarta de forma segura

El cliente MUST descartar (o migrar) el estado persistido de una versión anterior
cuyo shape es incompatible, en vez de rehidratarlo y romper la UI.

#### Scenario: Un deploy que cambia el shape no rompe al usuario
- **WHEN** el cliente arranca y encuentra estado persistido de una versión anterior con shape distinto
- **THEN** ese estado se descarta (o migra) según la versión declarada
- **AND** la aplicación arranca en un estado válido, sin datos corruptos
