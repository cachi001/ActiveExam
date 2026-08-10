# exam-content-model Specification

## MODIFIED Requirements

### Requirement: Modelo persistente de examen de contenido con preguntas y opciones
El sistema SHALL persistir el contenido de un examen en Postgres mediante un examen de contenido que agrupa preguntas, donde cada pregunta tiene un enunciado, un tipo (`multichoice` | `truefalse` | `cloze` como mínimo) y, según su tipo, un conjunto de opciones planas (opción múltiple) o un conjunto de blanks con sus opciones (cloze). Cada opción plana tiene un texto y una marca booleana de si es la opción correcta. Toda migración que amplíe el modelo (categorización, blanks de cloze) SHALL ser **aditiva** (rama slim, no toca tablas existentes) siguiendo el patrón de la migración `0023`: los exámenes ya importados SHALL seguir funcionando idénticos.

#### Scenario: Persistir un examen de contenido con sus preguntas y opciones
- **WHEN** se crea un examen de contenido con preguntas, cada una con sus opciones y la marca de cuál es correcta
- **THEN** el examen, sus preguntas y sus opciones quedan persistidos y recuperables, conservando qué opción es la correcta server-side

#### Scenario: Migración aditiva reversible
- **WHEN** se aplica la migración del modelo de contenido y luego se hace `alembic downgrade` a la revisión anterior
- **THEN** el downgrade dropea únicamente las tablas nuevas de contenido sin afectar las tablas existentes (proctoring_session, exam_config y demás)

## ADDED Requirements

### Requirement: Categorización aditiva de preguntas del banco
El sistema SHALL permitir clasificar cada pregunta del banco en **como máximo una** categoría del banco de preguntas mediante una columna `categoria_id` nullable en `pregunta_examen`, FK a `categoria_pregunta` ON DELETE SET NULL. La migración SHALL ser **aditiva**: una pregunta ya importada SHALL quedar con `categoria_id = NULL` ("Sin clasificar") por default, sin remodelado ni migración destructiva de `examen_contenido`/`pregunta_examen`. Borrar una categoría NUNCA SHALL borrar las preguntas: éstas SHALL quedar con `categoria_id = NULL`. El detalle de la jerarquía de categorías vive en `question-bank-categories`.

#### Scenario: La columna categoria_id es aditiva y nullable
- **WHEN** se aplica la migración que agrega `categoria_id` sobre una base con exámenes preexistentes
- **THEN** las preguntas existentes quedan con `categoria_id = NULL` y los exámenes siguen siendo válidos y rendibles sin cambios

#### Scenario: Borrar la categoría de una pregunta la deja sin clasificar
- **WHEN** se borra la categoría a la que apunta una pregunta
- **THEN** la pregunta persiste con `categoria_id = NULL` (SET NULL), no se borra

### Requirement: Integridad de una pregunta cloze en el modelo de contenido
Una pregunta de tipo `cloze` SHALL persistir su estructura en tablas propias de blanks (`pregunta_cloze_blank` / `opcion_cloze_blank`) y NO SHALL tener filas en `opcion_respuesta`. El sistema SHALL exigir al menos un blank por pregunta cloze y al menos una opción por blank con la marca de correcta correspondiente. La marca de correcta de las opciones de cada blank SHALL ser estado server-side, igual que en el modelo plano. El detalle de validación y grading vive en `cloze-question-type`.

#### Scenario: Una pregunta cloze usa tablas de blanks y no opcion_respuesta
- **WHEN** se persiste una pregunta `cloze`
- **THEN** su estructura queda en `pregunta_cloze_blank`/`opcion_cloze_blank` sin filas en `opcion_respuesta`, con la marca de correcta server-side por blank
