# ingesta-captura-binaria Specification

## Purpose
Que la captura de evidencia suba como bytes y no como texto, sin mover ni un hash.

Mandar la imagen dentro del JSON como data URL la infla un tercio: base64 son 4 bytes de
texto por cada 3 de imagen, y encima el JSON escapa el string. Medido contra el backend
real, una captura de 60 KB pasa de 80.131 a 60.437 bytes de subida (24,6% menos). Con 100
alumnos subiendo capturas durante dos horas por el enlace de su casa, ese tercio se paga
en tiempo de subida sobre la ruta crítica del examen.
## Requirements
### Requirement: La captura se puede ingestar en binario

El sistema SHALL aceptar un evento de detección con la imagen enviada como binario, con
los metadatos y el prefijo del data URL en partes separadas del mismo envío.

El camino de ingesta existente MUST seguir funcionando sin cambios: un cliente que no
migró tiene que poder seguir mandando evidencia.

#### Scenario: Evento con captura binaria

- **WHEN** se ingesta un evento con la imagen en binario y su prefijo
- **THEN** el evento se persiste y se responde con el mismo acuse que el camino existente

#### Scenario: Evento sin captura

- **WHEN** se ingesta un evento sin imagen
- **THEN** el evento se registra igual, sin hash de captura

### Requirement: El hash de la captura no cambia según el camino de ingesta

El sistema SHALL producir el mismo `screenshot_sha256` para una misma imagen,
independientemente de si se ingestó como texto o como binario.

El prefijo recibido MUST usarse tal cual para reconstruir el data URL, sin normalizar el
tipo de contenido: el hash se calcula sobre ese string y sostiene la cadena de custodia.
Un string que no se reconstruya byte a byte haría que la evidencia histórica deje de
verificar.

El sistema SHALL aceptar el prefijo con o sin el separador final, produciendo el mismo
hash en ambos casos.

#### Scenario: La misma imagen por los dos caminos

- **WHEN** se ingesta la misma imagen como texto y como binario
- **THEN** ambos eventos tienen idéntico `screenshot_sha256`

#### Scenario: Prefijo con separador final

- **WHEN** el prefijo llega con el separador incluido
- **THEN** el hash resultante es el mismo que sin él

#### Scenario: Tipo de contenido distinto de PNG

- **WHEN** se ingesta una imagen declarada con otro tipo de contenido
- **THEN** el hash corresponde a ese tipo, no a uno normalizado

### Requirement: La ingesta binaria conserva las garantías de la ingesta existente

El sistema SHALL aplicar al camino binario la misma verificación de pertenencia de sesión,
la misma re-inferencia server-side y el mismo cifrado at-rest que al camino existente.

La evidencia ingestada en binario SHALL poder recuperarse idéntica a como se envió.

#### Scenario: Sesión ajena

- **WHEN** se intenta ingestar en una sesión que no pertenece al principal
- **THEN** se rechaza igual que en el camino existente

#### Scenario: Sin credencial

- **WHEN** se intenta ingestar sin token
- **THEN** se responde no autorizado

#### Scenario: La evidencia se recupera

- **WHEN** un revisor abre la sesión
- **THEN** ve la captura idéntica a la que envió el cliente

