# student-dashboard-landing Specification

## Purpose
TBD - created by archiving change c-21-portal-alumno-materias-inscripcion. Update Purpose after archive.
## Requirements
### Requirement: El alumno aterriza en el dashboard tras el login
Tras autenticarse con rol `estudiante`, el sistema SHALL redirigir al alumno a `/alumno/dashboard` en lugar de `/requisitos`. El dashboard SHALL mostrar un resumen de: próximos exámenes con inscripción activa, materias en curso y el estado de completitud del perfil.

#### Scenario: Redirección post-login
- **WHEN** el usuario completa el login con rol `estudiante`
- **THEN** la aplicación navega a `/alumno/dashboard` y no a `/requisitos`

#### Scenario: Dashboard muestra próximos exámenes
- **WHEN** el alumno tiene inscripciones en estado `inscripto` o `habilitado`
- **THEN** el dashboard muestra una sección "Próximos exámenes" con nombre del examen, materia, fecha y estado de inscripción

#### Scenario: Dashboard muestra alerta de perfil incompleto
- **WHEN** `puedeRendir().puede` es `false`
- **THEN** el dashboard muestra un banner de advertencia indicando que el perfil está incompleto y un enlace a `/alumno/perfil`

#### Scenario: Dashboard muestra acceso rápido a materias
- **WHEN** el alumno está en el dashboard
- **THEN** existe un acceso rápido a "Mis materias" que navega a `/alumno/materias`

### Requirement: El dashboard refleja datos de UTN FRM
El sistema SHALL mostrar en el dashboard datos de demo correspondientes a UTN Regional Mendoza: cátedras de ingeniería, emails `@frm.utn.edu.ar` y el nombre institucional correcto.

#### Scenario: Datos del alumno con dominio UTN FRM
- **WHEN** el alumno accede al dashboard
- **THEN** su email institucional muestra dominio `@frm.utn.edu.ar` y la institución "UTN Regional Mendoza"

