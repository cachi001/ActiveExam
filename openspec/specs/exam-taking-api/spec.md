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

