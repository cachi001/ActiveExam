# enrollment-render-gate Specification

## Purpose
TBD - created by archiving change c-71-inscripcion-gate-y-cola-revision. Update Purpose after archive.
## Requirements
### Requirement: El catálogo de materias del alumno se filtra por sus inscripciones
El sistema SHALL mostrar en "Mis materias" ÚNICAMENTE las materias/comisiones donde el alumno (principal del JWT) está inscripto, derivándolas de la tabla `inscripcion` por `usuario_id`. Un alumno sin inscripciones SHALL ver una lista vacía con una invitación a matricularse por código. La lista NO SHALL derivarse de catálogos hardcodeados ni del conjunto total de comisiones.

#### Scenario: Alumno inscripto ve solo sus comisiones
- **WHEN** el alumno está inscripto en la comisión C1 de la materia PROG1 y en ninguna otra
- **THEN** "Mis materias" muestra PROG1 · C1 y ninguna otra materia/comisión

#### Scenario: Alumno sin inscripciones ve la lista vacía
- **WHEN** el alumno no tiene ninguna fila en `inscripcion`
- **THEN** "Mis materias" no muestra ninguna materia
- **THEN** se ofrece matricularse ingresando un código de matriculación

### Requirement: El catálogo de exámenes del alumno se filtra por comisión inscripta
El sistema SHALL listar en "Exámenes disponibles" ÚNICAMENTE los exámenes cuyas comisiones (`examen_contenido.comision_id`) figuran entre las inscripciones del alumno. Un examen de una comisión donde el alumno NO está inscripto NO SHALL aparecer en el catálogo del alumno. El filtrado SHALL ejecutarse server-side por `usuario_id`; el rol admin conserva la vista completa del catálogo.

#### Scenario: El examen de una comisión no inscripta no aparece
- **WHEN** existe "Examen de Programación 1" en la comisión C1 y el alumno NO está inscripto en C1
- **THEN** "Exámenes disponibles" del alumno no incluye ese examen

#### Scenario: El examen de una comisión inscripta aparece
- **WHEN** el alumno se matricula en C1 por código y C1 tiene "Examen de Programación 1"
- **THEN** "Exámenes disponibles" del alumno incluye ese examen

### Requirement: Backstop server-side de inscripción al crear la sesión de rendición
El sistema SHALL rechazar la creación de una sesión de proctoring vinculada a un `examen_contenido_id` si el alumno (principal del JWT) NO está inscripto en la comisión de ese examen, respondiendo 403 con un error identificable (`no_inscripto`). Este control SHALL ser independiente del filtrado del catálogo en el frontend (el cliente es sensor no confiable): aunque el alumno invoque la API directamente, sin inscripción no se crea la sesión.

#### Scenario: Crear sesión sin inscripción es rechazado server-side
- **WHEN** un alumno sin inscripción en la comisión del examen invoca `POST /sessions` con ese `examen_contenido_id`
- **THEN** el backend responde 403 con `error = "no_inscripto"`
- **THEN** no se crea ninguna sesión

#### Scenario: Crear sesión con inscripción y perfil completo procede
- **WHEN** un alumno inscripto en la comisión del examen y con perfil completo invoca `POST /sessions`
- **THEN** el backend crea la sesión (sujeto además al enforcement de ventana e intentos ya existente)

