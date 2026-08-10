# cloze-question-type Specification

## Purpose
TBD - created by archiving change c-74-banco-preguntas-categorias-cloze. Update Purpose after archive.
## Requirements
### Requirement: Modelo de datos de preguntas cloze con blanks
El sistema SHALL persistir preguntas de tipo `cloze` mediante tablas nuevas y aditivas: `pregunta_cloze_blank` (id, `pregunta_id` FK a `pregunta_examen`, orden, tipo [`multichoice` | `shortanswer` | `numerical`], texto_antes, texto_despues) y `opcion_cloze_blank` (id, `blank_id` FK, texto, es_correcta, peso). Una pregunta `cloze` SHALL tener N filas en `pregunta_cloze_blank` y NO SHALL tener filas en `opcion_respuesta` (que sigue siendo exclusiva del modelo plano 1 pregunta → N opciones). La migración SHALL ser aditiva y no remodelar el modelo plano existente.

#### Scenario: Persistir una pregunta cloze con sus blanks y opciones
- **WHEN** se crea una pregunta `cloze` con varios blanks, cada uno con sus opciones y la marca de correcta
- **THEN** la pregunta, sus blanks y las opciones de cada blank quedan persistidos en `pregunta_cloze_blank`/`opcion_cloze_blank`, sin filas en `opcion_respuesta`

#### Scenario: El modelo plano no se ve afectado
- **WHEN** coexisten preguntas `cloze` y preguntas `multichoice`/`truefalse` en el mismo examen
- **THEN** las preguntas de opción múltiple siguen usando `opcion_respuesta` y las cloze usan sus tablas de blanks, sin interferencia

### Requirement: Validación de dominio de una pregunta cloze
El sistema SHALL validar en el dominio (`Pregunta.__post_init__`) que una pregunta `cloze` tiene al menos un blank, que cada blank tiene al menos una opción, y que cada blank tiene exactamente una opción marcada como correcta (o más de una si el tipo del blank lo permite). El sistema SHALL rechazar la creación de una pregunta cloze que viole estas reglas.

#### Scenario: Cloze sin blanks o con un blank sin correcta es rechazada
- **WHEN** se intenta persistir una pregunta `cloze` sin blanks, o con un blank sin ninguna opción marcada como correcta
- **THEN** el sistema rechaza la operación con un error de validación de dominio y la pregunta no se persiste

### Requirement: Grading parcial por blank
El sistema SHALL calificar las preguntas `cloze` de forma **parcial por blank**, no todo-o-nada: recibe `{pregunta_id: {blank_id: opcion_elegida_id}}` y calcula la nota de la pregunta como (blanks correctos / blanks totales) × peso de la pregunta. Un blank sin respuesta SHALL contar como incorrecto y NO SHALL romper el cálculo.

#### Scenario: Cloze con parte de los blanks correctos obtiene nota parcial
- **WHEN** un alumno responde una pregunta cloze de 4 blanks con 3 correctos y 1 incorrecto
- **THEN** la nota de esa pregunta es el 75% de su peso, no 0

#### Scenario: Blank vacío cuenta como incorrecto sin romper el cálculo
- **WHEN** un alumno deja un blank sin responder
- **THEN** ese blank se computa como incorrecto y el cálculo de la nota completa la pregunta sin error

### Requirement: Render de rendición de preguntas cloze
El sistema SHALL renderizar una pregunta `cloze` como un enunciado continuo con los placeholders reemplazados por **controles embebidos inline** (selects/inputs dentro del texto), NO como una lista de radios debajo del enunciado. El estado de respuesta guardada SHALL soportar la forma jerárquica `Record<pregunta_id, string | Record<blank_id, string>>` sin romper el camino no-cloze existente (un valor plano por pregunta). Las respuestas cloze SHALL persistir con el mismo contrato de autoguardado que las preguntas normales.

#### Scenario: Renderizar cloze con controles embebidos en el texto
- **WHEN** el alumno abre una pregunta `cloze`
- **THEN** ve el enunciado con los huecos reemplazados por controles inline, no una lista de radios separada del texto

#### Scenario: Las respuestas cloze persisten al recargar
- **WHEN** el alumno responde los blanks de una pregunta cloze y recarga la página
- **THEN** las respuestas de cada blank persisten, con el mismo contrato de autoguardado que las preguntas normales

