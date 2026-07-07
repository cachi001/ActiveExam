# Spec — exam-content-model

> Modelo de dominio y persistencia (Postgres slim, Alembic aditivo) del CONTENIDO de un examen: examen de contenido, preguntas, opciones y marca de opción correcta. Separado de la configuración de proctoring existente (`exam_config`). Materializa el cambio de postura que anula DD-20 (la plataforma ahora opera el examen).

## ADDED Requirements

### Requirement: Modelo persistente de examen de contenido con preguntas y opciones
El sistema SHALL persistir el contenido de un examen en Postgres mediante un examen de contenido que agrupa preguntas, donde cada pregunta tiene un enunciado, un tipo (`multichoice` | `truefalse` como mínimo) y un conjunto de opciones, y cada opción tiene un texto y una marca booleana de si es la opción correcta. La migración SHALL ser **aditiva** (rama slim, no toca tablas existentes) siguiendo el patrón de la migración `0023`.

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
El sistema SHALL persistir **materia** (con `codigo` único y `nombre`) y **comisión** (con `codigo`, `nombre`, una FK obligatoria a su materia y, opcionalmente, período/cuatrimestre y año). Una comisión SHALL pertenecer a **exactamente una** materia. La combinación (`materia_id`, `codigo`) de una comisión SHALL ser única. Materia y comisión son un requisito real del producto (se modelan y persisten, NO se difieren a otro change), pero su asociación con un examen es **opcional en el MVP** (ver requisito siguiente). La migración SHALL ser **aditiva** (rama slim, no toca tablas existentes), siguiendo el patrón de `0023`.

#### Scenario: Persistir una materia con sus comisiones
- **WHEN** se crea una materia y una comisión que la referencia
- **THEN** la materia y la comisión quedan persistidas y recuperables, y la comisión queda ligada a exactamente esa materia

#### Scenario: La combinación materia + código de comisión es única
- **WHEN** se intenta persistir una segunda comisión con el mismo `codigo` dentro de la misma materia
- **THEN** el sistema rechaza la operación por violación de unicidad de (`materia_id`, `codigo`)

#### Scenario: Una comisión no puede existir sin materia
- **WHEN** se intenta persistir una comisión sin materia asociada
- **THEN** el sistema rechaza la operación: toda comisión pertenece a exactamente una materia

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
