## MODIFIED Requirements

### Requirement: Modelo persistente de examen de contenido con preguntas y opciones
El sistema SHALL persistir el contenido de un examen en Postgres mediante un examen de contenido que agrupa preguntas, donde cada pregunta tiene un enunciado, un tipo (`multichoice` | `truefalse` | `cloze` como mínimo) y, según su tipo, un conjunto de opciones planas (opción múltiple) o un conjunto de blanks con sus opciones (cloze). Cada opción plana tiene un texto y una marca booleana de si es la opción correcta.

El examen de contenido SHALL tener además un **estado de baja lógica** representado por la columna nullable `eliminado_en` (`NULL` = activo, `NOT NULL` = dado de baja, con el timestamp de la baja), siguiendo la misma convención ya vigente en `usuario`, `sesion`, `embedding_referencia` y `foto_referencia`. El examen dado de baja SHALL conservarse íntegro en la base: la baja NO SHALL borrar la fila ni sus preguntas, opciones, sesiones o evidencia asociadas.

Toda migración que amplíe el modelo (categorización, blanks de cloze, baja lógica) SHALL ser **aditiva** (rama activeexam, no toca tablas existentes) siguiendo el patrón de la migración `0023`: los exámenes ya importados SHALL seguir funcionando idénticos.

#### Scenario: Persistir un examen de contenido con sus preguntas y opciones
- **WHEN** se crea un examen de contenido con preguntas, cada una con sus opciones y la marca de cuál es correcta
- **THEN** el examen, sus preguntas y sus opciones quedan persistidos y recuperables, conservando qué opción es la correcta server-side

#### Scenario: Un examen recién creado nace activo
- **WHEN** se crea o importa un examen de contenido
- **THEN** su `eliminado_en` es NULL

#### Scenario: Los exámenes preexistentes quedan activos tras la migración
- **WHEN** se aplica la migración que agrega `eliminado_en` sobre una base con exámenes ya cargados
- **THEN** todos esos exámenes quedan con `eliminado_en` en NULL y siguen apareciendo en los listados sin ningún backfill

#### Scenario: Migración aditiva reversible
- **WHEN** se aplica la migración del modelo de contenido y luego se hace `alembic downgrade` a la revisión anterior
- **THEN** el downgrade dropea únicamente las columnas y tablas nuevas de contenido sin afectar las tablas existentes (proctoring_session, exam_config y demás)
