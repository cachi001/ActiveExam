# exam-taking-api Specification

## Purpose
TBD - created by archiving change c-69-examen-plataforma-moodle-lockdown. Update Purpose after archive.
## Requirements
### Requirement: Endpoint de lectura de examen para rendir
El sistema SHALL exponer bajo `/api/v1` un endpoint de lectura que, dado un examen de contenido, devuelve sus preguntas y, para cada pregunta, sus opciones (texto + identificador de opción), en un orden estable. Los schemas de respuesta SHALL usar Pydantic con `model_config = ConfigDict(extra='forbid')`.

#### Scenario: El alumno habilitado obtiene las preguntas para rendir
- **WHEN** un alumno habilitado solicita el examen de contenido a rendir
- **THEN** el sistema devuelve las preguntas y sus opciones en un orden estable, suficientes para renderizar la rendición

#### Scenario: Orden estable de preguntas y opciones
- **WHEN** se solicita el mismo examen dos veces
- **THEN** el orden de las preguntas y de sus opciones es el mismo en ambas respuestas (determinístico)

### Requirement: La respuesta de rendición NUNCA incluye la opción correcta
La proyección devuelta por el endpoint de rendición SHALL NOT incluir, para ninguna opción, la marca ni indicación de cuál es la correcta. El cliente del alumno SHALL ser incapaz de derivar la respuesta correcta a partir de la respuesta de red (regla dura: cliente = sensor no confiable).

#### Scenario: La opción correcta no viaja al cliente
- **WHEN** el alumno solicita el examen para rendir y se inspecciona la respuesta de red
- **THEN** ninguna opción de ninguna pregunta expone si es la correcta

### Requirement: Examen inexistente devuelve 404
El endpoint de rendición SHALL devolver 404 cuando el examen de contenido solicitado no existe.

#### Scenario: Examen inexistente
- **WHEN** se solicita un examen de contenido cuyo identificador no existe
- **THEN** el sistema responde 404 sin filtrar datos de otros exámenes

### Requirement: El envío de respuestas revalida el plazo server-side

El endpoint de envío de respuestas SHALL rechazar con `409 tiempo_agotado` toda respuesta recibida después del deadline efectivo más el margen de gracia, y SHALL NOT persistir ninguna de las respuestas del envío rechazado. Esta validación SHALL ser independiente del enforcement que ocurre al crear la sesión: el hecho de que una rendición haya arrancado válidamente NO SHALL habilitarla a mutar indefinidamente (regla dura de dominio #6 — el cliente que informa la hora es el mismo que rinde).

#### Scenario: Respuesta pasado el límite individual

- **WHEN** un alumno envía una respuesta 140 minutos después de haber arrancado un examen con `tiempo_limite_min = 40`
- **THEN** el sistema responde `409 tiempo_agotado` y no persiste la respuesta

#### Scenario: Respuesta con la ventana del examen ya cerrada

- **WHEN** un alumno envía una respuesta para un examen cuya ventana cerró hace un día, sobre una sesión que arrancó dentro de la ventana
- **THEN** el sistema responde `409 tiempo_agotado` y no persiste la respuesta

#### Scenario: Respuesta dentro del plazo se persiste

- **WHEN** un alumno envía una respuesta antes del deadline efectivo
- **THEN** el sistema persiste la respuesta y responde 201

#### Scenario: Rechazo atómico del lote

- **WHEN** un envío fuera de plazo contiene varias respuestas
- **THEN** ninguna de las respuestas del lote se persiste

### Requirement: El rechazo por plazo es distinguible del rechazo por sesión finalizada

El sistema SHALL diferenciar en la respuesta de error el rechazo por vencimiento del plazo (`tiempo_agotado`) del rechazo por sesión ya entregada (`sesion_finalizada`), de modo que la interfaz del alumno pueda explicar con precisión qué ocurrió y SHALL NOT perder respuestas de forma silenciosa.

#### Scenario: Error de plazo identificable

- **WHEN** el envío se rechaza por vencimiento del deadline efectivo
- **THEN** el cuerpo del error identifica el caso como `tiempo_agotado`

#### Scenario: Error de sesión entregada identificable

- **WHEN** el envío se rechaza porque la sesión ya fue finalizada
- **THEN** el cuerpo del error identifica el caso como `sesion_finalizada`

