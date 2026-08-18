# exam-content-model Specification

## Purpose
TBD - created by archiving change c-69-examen-plataforma-moodle-lockdown. Update Purpose after archive.
## Requirements
### Requirement: Modelo persistente de examen de contenido con preguntas y opciones
El sistema SHALL persistir el contenido de un examen en Postgres mediante un examen de contenido que agrupa preguntas, donde cada pregunta tiene un enunciado, un tipo (`multichoice` | `truefalse` | `cloze` como mínimo) y, según su tipo, un conjunto de opciones planas (opción múltiple) o un conjunto de blanks con sus opciones (cloze). Cada opción plana tiene un texto y una marca booleana de si es la opción correcta. Toda migración que amplíe el modelo (categorización, blanks de cloze) SHALL ser **aditiva** (rama activeexam, no toca tablas existentes) siguiendo el patrón de la migración `0023`: los exámenes ya importados SHALL seguir funcionando idénticos.

#### Scenario: Persistir un examen de contenido con sus preguntas y opciones
- **WHEN** se crea un examen de contenido con preguntas, cada una con sus opciones y la marca de cuál es correcta
- **THEN** el examen, sus preguntas y sus opciones quedan persistidos y recuperables, conservando qué opción es la correcta server-side

#### Scenario: Migración aditiva reversible
- **WHEN** se aplica la migración del modelo de contenido y luego se hace `alembic downgrade` a la revisión anterior
- **THEN** el downgrade dropea únicamente las tablas nuevas de contenido sin afectar las tablas existentes (proctoring_session, exam_config y demás)

### Requirement: Integridad de una pregunta de opción múltiple
Una pregunta de tipo `multichoice` SHALL tener al menos dos opciones y exactamente una opción marcada como correcta; una pregunta `truefalse` SHALL tener exactamente dos opciones con exactamente una correcta. El sistema SHALL rechazar la creación de una pregunta que viole estas reglas.

#### Scenario: Pregunta sin opción correcta es rechazada
- **WHEN** se intenta persistir una pregunta de opción múltiple sin ninguna opción marcada como correcta, o con más de una correcta
- **THEN** el sistema rechaza la operación con un error de validación de dominio y la pregunta no se persiste

#### Scenario: Pregunta de opción múltiple con menos de dos opciones es rechazada
- **WHEN** se intenta persistir una pregunta `multichoice` con menos de dos opciones
- **THEN** el sistema rechaza la operación con un error de validación de dominio

### Requirement: La marca de opción correcta es estado server-side
La marca de opción correcta SHALL almacenarse y permanecer del lado del servidor y SHALL usarse únicamente para corrección server-side; NUNCA SHALL formar parte de una proyección destinada al cliente del alumno (ver capability `exam-taking-api`).

#### Scenario: La opción correcta no se expone en lecturas del alumno
- **WHEN** se construye la proyección de un examen para que el alumno lo rinda
- **THEN** la proyección no incluye la marca de opción correcta de ninguna opción

### Requirement: Modelo persistente de materia y comisión
El sistema SHALL persistir **materia** (con `codigo` único y `nombre`) y **comisión** (con `codigo`, `nombre`, una FK obligatoria a su materia, opcionalmente período/cuatrimestre y año, y un `codigo_matriculacion` **único** a nivel global). Una comisión SHALL pertenecer a **exactamente una** materia. La combinación (`materia_id`, `codigo`) de una comisión SHALL ser única. El `codigo_matriculacion` SHALL ser único entre todas las comisiones, SHALL autogenerarse a partir del `codigo` de la materia con un sufijo aleatorio corto cuando no se provee, y SHALL ser editable por el docente (ver capability `matriculacion-por-codigo`). Materia y comisión son un requisito real del producto (se modelan y persisten, NO se difieren a otro change), pero su asociación con un examen es **opcional en el MVP** (ver requisito siguiente). La migración que agrega `codigo_matriculacion` SHALL ser **aditiva** (rama activeexam, no toca tablas existentes) y **en dos pasos** para poder aplicar unicidad sobre filas existentes: agregar la columna nullable, backfillear un código único por comisión existente y luego aplicar la restricción `UNIQUE`.

#### Scenario: Persistir una materia con sus comisiones
- **WHEN** se crea una materia y una comisión que la referencia
- **THEN** la materia y la comisión quedan persistidas y recuperables, y la comisión queda ligada a exactamente esa materia

#### Scenario: La combinación materia + código de comisión es única
- **WHEN** se intenta persistir una segunda comisión con el mismo `codigo` dentro de la misma materia
- **THEN** el sistema rechaza la operación por violación de unicidad de (`materia_id`, `codigo`)

#### Scenario: Una comisión no puede existir sin materia
- **WHEN** se intenta persistir una comisión sin materia asociada
- **THEN** el sistema rechaza la operación: toda comisión pertenece a exactamente una materia

#### Scenario: La comisión persiste un código de matriculación único
- **WHEN** se crea una comisión (con o sin `codigo_matriculacion` provisto)
- **THEN** la comisión queda persistida con un `codigo_matriculacion` no nulo y único entre todas las comisiones

#### Scenario: Migración aditiva en dos pasos backfillea las comisiones existentes
- **WHEN** se aplica la migración que agrega `codigo_matriculacion` sobre una base con comisiones preexistentes
- **THEN** cada comisión existente recibe un `codigo_matriculacion` único generado durante el backfill
- **THEN** la restricción `UNIQUE` queda aplicada sin violar la unicidad de las filas backfilleadas
- **THEN** el `alembic downgrade` remueve la columna sin afectar otras tablas

### Requirement: La asociación examen→comisión es opcional en el MVP
Un examen de contenido SHALL tener una FK a comisión que es **NULLABLE**. Un examen SIN comisión asignada SHALL ser un estado **válido** (estado MVP): el examen se puede importar, persistir y rendir sin comisión ni materia. Cuando un examen TIENE comisión, SHALL referenciar **exactamente una**, y a través de ella SHALL derivar transitivamente su materia. El admin PUEDE asignar (o cambiar) la comisión de un examen después de importarlo.

#### Scenario: Un examen sin comisión es válido y persistente
- **WHEN** se crea o importa un examen de contenido sin indicar comisión (FK `comision_id` en NULL)
- **THEN** el examen queda persistido, recuperable y rendible, sin materia ni comisión, sin error de validación

#### Scenario: Un examen con comisión deriva su materia transitivamente
- **WHEN** un examen de contenido tiene una comisión asignada
- **THEN** referencia exactamente una comisión y, a través de ella, su materia queda determinada de forma transitiva

#### Scenario: Asignar la comisión de un examen después de importarlo
- **WHEN** el admin asigna una comisión a un examen que se había importado sin ella
- **THEN** el examen queda ligado a esa comisión (y por transitividad a su materia), sin necesidad de reimportar el contenido

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

