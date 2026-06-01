# student-portal-navigation Specification

## Purpose
TBD - created by archiving change c-21-portal-alumno-materias-inscripcion. Update Purpose after archive.
## Requirements
### Requirement: El mock define la jerarquía Materia → Comision → Examen
El sistema SHALL modelar los tipos `Materia`, `Comision` e `Inscripcion` en `lib/types.ts`. Una `Materia` tiene una o más `Comision`es. Una `Comision` tiene uno o más `Examen`es asociados via `comision_id`. Los datos de demo SHALL representar cátedras de ingeniería de UTN FRM.

#### Scenario: Tipos disponibles en tiempo de compilación
- **WHEN** el compilador TypeScript procesa el proyecto (`tsc --noEmit`)
- **THEN** los tipos `Materia`, `Comision`, `Inscripcion` y `EstadoInscripcion` están disponibles desde `lib/types.ts` sin errores de tipo

#### Scenario: API mock retorna materias disponibles
- **WHEN** se llama `api.materiasDisponibles()`
- **THEN** retorna una lista de `Materia[]` con al menos 3 materias de ingeniería de UTN FRM con `id`, `nombre` y `codigo`

#### Scenario: API mock retorna comisiones de una materia
- **WHEN** se llama `api.comisionesDeMateria(materiaId)` con un id válido
- **THEN** retorna `Comision[]` con al menos una comisión para esa materia, con `id`, `nombre`, `docente` y `materia_id`

#### Scenario: API mock retorna exámenes de una comisión
- **WHEN** se llama `api.examenesDeComision(comisionId)` con un id válido
- **THEN** retorna `Examen[]` (tipo existente) asociados a esa comisión

### Requirement: La pantalla de materias permite la navegación jerárquica
El sistema SHALL proveer la pantalla `/alumno/materias` que muestre la lista de materias disponibles. Al seleccionar una materia, SHALL mostrar sus comisiones. Al seleccionar una comisión, SHALL mostrar los exámenes disponibles con su estado y botón de inscripción cuando corresponda.

#### Scenario: Navegación a lista de materias
- **WHEN** el alumno navega a `/alumno/materias`
- **THEN** se renderiza una lista de materias con nombre y código de asignatura

#### Scenario: Expansión de comisiones de una materia
- **WHEN** el alumno selecciona una materia en la pantalla `/alumno/materias`
- **THEN** se muestran las comisiones disponibles con nombre del docente y horario

#### Scenario: Vista de exámenes de una comisión
- **WHEN** el alumno selecciona una comisión
- **THEN** se muestran los exámenes de esa comisión con nombre, fecha, duración y estado del examen (`programado`, `en_curso`, `finalizado`)

#### Scenario: Examen sin inscripción muestra botón "Inscribirme"
- **WHEN** el examen tiene estado `programado` y el alumno no está inscripto
- **THEN** se muestra el botón "Inscribirme" habilitado

#### Scenario: Examen ya inscripto no muestra botón de inscripción
- **WHEN** el alumno ya tiene una inscripción activa para ese examen
- **THEN** se muestra el badge "Inscripto" en lugar del botón "Inscribirme"

