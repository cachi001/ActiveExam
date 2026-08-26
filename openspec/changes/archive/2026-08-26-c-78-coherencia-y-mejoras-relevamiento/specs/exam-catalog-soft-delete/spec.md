## ADDED Requirements

### Requirement: Baja lógica de un examen del catálogo
El sistema SHALL permitir dar de baja un examen de contenido mediante `DELETE /api/v1/exam-content/{examen_id}`, seteando `eliminado_en = now()` sobre la fila de `examen_contenido`. La fila NO SHALL borrarse físicamente. La operación SHALL requerir la capacidad `gestionar_academico` y SHALL responder `204 No Content`.

Un examen ya dado de baja SHALL responder `404` a un nuevo intento de baja (mismo contrato que `DELETE /users/{id}`).

#### Scenario: Baja de un examen activo
- **WHEN** un usuario con `gestionar_academico` invoca `DELETE /api/v1/exam-content/{id}` sobre un examen con `eliminado_en` en NULL
- **THEN** la respuesta es `204`, la fila persiste en la base y `eliminado_en` queda con el timestamp de la operación

#### Scenario: Baja de un examen ya dado de baja
- **WHEN** se invoca la baja sobre un examen cuyo `eliminado_en` ya es NOT NULL
- **THEN** la respuesta es `404` y la fila no se modifica

#### Scenario: Sin permiso no se da de baja
- **WHEN** un usuario sin la capacidad `gestionar_academico` invoca la baja
- **THEN** el acceso es rechazado y el examen sigue activo

### Requirement: Reactivación de un examen dado de baja
El sistema SHALL permitir reactivar un examen mediante `POST /api/v1/exam-content/{examen_id}/reactivar`, seteando `eliminado_en = NULL`. SHALL requerir la capacidad `gestionar_academico`. Un examen que ya está activo SHALL responder `404`.

#### Scenario: Reactivación de un examen dado de baja
- **WHEN** se invoca `POST /api/v1/exam-content/{id}/reactivar` sobre un examen con `eliminado_en` NOT NULL
- **THEN** `eliminado_en` vuelve a NULL y el examen reaparece en los listados con filtro de estado por defecto

#### Scenario: Reactivación de un examen activo
- **WHEN** se invoca la reactivación sobre un examen que ya está activo
- **THEN** la respuesta es `404` y la fila no se modifica

### Requirement: La baja no altera la evidencia ni la actividad histórica
Dar de baja o reactivar un examen SHALL ser una operación exclusivamente administrativa sobre el catálogo. Las sesiones de proctoring, eventos, capturas de evidencia, notas persistidas y decisiones de revisión asociadas a ese examen SHALL permanecer intactas y consultables por id, conforme a las reglas de cadena de custodia del proyecto.

Las métricas de **actividad** (sesiones iniciadas, sesiones finalizadas, distribución de scores) SHALL seguir contando las sesiones de un examen dado de baja: la actividad ocurrió y es un hecho histórico. Solo las métricas de **inventario** (conteo de exámenes del catálogo) SHALL excluirlo.

#### Scenario: La evidencia sobrevive a la baja
- **WHEN** se da de baja un examen que tiene sesiones rendidas con evidencia
- **THEN** esas sesiones, sus eventos y sus capturas siguen existiendo y siguen siendo consultables por id

#### Scenario: La actividad histórica no cae
- **WHEN** se da de baja un examen que tiene sesiones rendidas
- **THEN** el total de sesiones reportado por Estadísticas NO cambia

#### Scenario: El inventario sí cae
- **WHEN** se da de baja un examen
- **THEN** el conteo de exámenes del catálogo reportado por Estadísticas se reduce en uno

### Requirement: Filtro de estado en el catálogo de exámenes
`GET /api/v1/exam-content` SHALL aceptar un parámetro `estado` con valores `activo` (default) | `inactivo` | `todos`, con la misma semántica que `GET /users`: `activo` devuelve solo los exámenes con `eliminado_en` en NULL, `inactivo` solo los dados de baja, `todos` ambos. El filtrado SHALL resolverse en SQL, y el `total` de la respuesta paginada SHALL corresponder al conjunto filtrado.

Todo consumidor del catálogo que no especifique `estado` SHALL recibir únicamente exámenes activos.

#### Scenario: Listado por defecto oculta los dados de baja
- **WHEN** se pide `GET /api/v1/exam-content` sin `estado`
- **THEN** los exámenes con `eliminado_en` NOT NULL no aparecen en `items` ni se cuentan en `total`

#### Scenario: Listado de dados de baja
- **WHEN** se pide `GET /api/v1/exam-content?estado=inactivo`
- **THEN** se devuelven únicamente los exámenes con `eliminado_en` NOT NULL

#### Scenario: Listado completo
- **WHEN** se pide `GET /api/v1/exam-content?estado=todos`
- **THEN** se devuelven activos y dados de baja, y `total` los cuenta a ambos

#### Scenario: El picker en cascada de Notas no ofrece exámenes dados de baja
- **WHEN** se listan los exámenes de una comisión para el selector de Notas
- **THEN** los exámenes dados de baja no aparecen entre las opciones

### Requirement: La pantalla de Exámenes opera la baja y la reactivación
La pantalla **Exámenes** SHALL ofrecer un filtro de estado (activo / dado de baja / todos) que mande el parámetro `estado` al backend, y SHALL ofrecer en el menú de acciones de cada fila la baja (para un examen activo) o la reactivación (para uno dado de baja). La baja SHALL pedir confirmación explícita antes de ejecutarse, e informar que el examen se oculta del catálogo pero su evidencia se conserva.

#### Scenario: Dar de baja desde la lista
- **WHEN** el usuario elige "Dar de baja" en el menú de acciones de un examen activo y confirma
- **THEN** se invoca el `DELETE`, la lista se recarga y el examen deja de aparecer bajo el filtro por defecto

#### Scenario: Ver y reactivar un examen dado de baja
- **WHEN** el usuario aplica el filtro de estado "dado de baja" y elige "Reactivar" sobre una fila
- **THEN** se invoca la reactivación y el examen vuelve a aparecer bajo el filtro por defecto

#### Scenario: La baja pide confirmación
- **WHEN** el usuario elige "Dar de baja" y cancela la confirmación
- **THEN** no se invoca ningún endpoint y el examen sigue activo

### Requirement: La baja y la reactivación quedan auditadas
Cada baja y cada reactivación de examen SHALL registrar una entrada en el audit log con actor, timestamp, la entidad y su id, y un propósito legible, siguiendo el patrón ya usado por la baja de materia y comisión. El registro SHALL ser best-effort respecto de la operación (un fallo de auditoría no revierte la baja) y SHALL loguearse a nivel error si falla.

#### Scenario: Baja auditada
- **WHEN** un examen se da de baja correctamente
- **THEN** el audit log contiene una entrada con el actor, el id del examen y el módulo de exámenes

#### Scenario: Reactivación auditada
- **WHEN** un examen se reactiva correctamente
- **THEN** el audit log contiene una entrada distinguible de la de baja, con el actor y el id del examen

#### Scenario: La acción es filtrable desde Auditoría
- **WHEN** se filtra el registro de actividad por la acción de baja/reactivación de examen
- **THEN** las entradas correspondientes aparecen en el listado
