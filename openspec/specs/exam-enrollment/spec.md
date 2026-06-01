# exam-enrollment Specification

## Purpose
TBD - created by archiving change c-21-portal-alumno-materias-inscripcion. Update Purpose after archive.
## Requirements
### Requirement: El alumno puede inscribirse a un examen programado
El sistema SHALL permitir al alumno inscribirse a un examen con estado `programado` mediante `api.inscribir(examenId)`. La operación SHALL crear una `Inscripcion` con estado inicial `inscripto` en el registro in-memory del mock.

#### Scenario: Inscripción exitosa
- **WHEN** el alumno hace clic en "Inscribirme" para un examen con estado `programado`
- **THEN** `api.inscribir(examenId)` retorna la `Inscripcion` creada con estado `inscripto`
- **THEN** el botón "Inscribirme" se reemplaza por el badge "Inscripto" en la UI

#### Scenario: No se puede inscribir a un examen finalizado
- **WHEN** el examen tiene estado `finalizado`
- **THEN** el botón "Inscribirme" no se muestra y el estado se muestra como no disponible

#### Scenario: Inscripción duplicada no crea un registro nuevo
- **WHEN** el alumno ya tiene una inscripción activa para ese examen
- **THEN** `api.inscribir(examenId)` retorna la inscripción existente sin crear un duplicado

### Requirement: La pantalla "Mis exámenes" muestra el registro de inscripciones
El sistema SHALL proveer la pantalla `/alumno/mis-examenes` que liste todas las inscripciones del alumno con su estado y la acción siguiente disponible. El estado SHALL ser uno de: `inscripto`, `pendiente`, `habilitado`, `rendido`.

#### Scenario: Lista de inscripciones visible
- **WHEN** el alumno navega a `/alumno/mis-examenes`
- **THEN** se renderiza la lista de inscripciones retornada por `api.misInscripciones()`

#### Scenario: Inscripción con estado "habilitado" y perfil completo muestra acción "Rendir"
- **WHEN** una inscripción tiene estado `habilitado` y `puedeRendir().puede` es `true`
- **THEN** se muestra el botón "Rendir" que navega al flujo existente iniciando en `/requisitos`

#### Scenario: Inscripción con estado "habilitado" y perfil incompleto muestra acción "Completar perfil"
- **WHEN** una inscripción tiene estado `habilitado` y `puedeRendir().puede` es `false`
- **THEN** se muestra el botón "Completar perfil" que navega a `/alumno/perfil`
- **THEN** no se muestra el botón "Rendir"

#### Scenario: Inscripción con estado "rendido" muestra resultado
- **WHEN** una inscripción tiene estado `rendido`
- **THEN** se muestra el badge "Rendido" sin botón de acción primaria

#### Scenario: Lista vacía muestra mensaje de ayuda
- **WHEN** el alumno no tiene inscripciones registradas
- **THEN** la pantalla muestra un mensaje invitando a inscribirse en `/alumno/materias`

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL evaluar `api.puedeRendir()` antes de permitir el inicio del flujo de examen. Si el resultado es `{ puede: false }`, el sistema SHALL redirigir al alumno a `/alumno/perfil` en lugar de iniciar el flujo de requisitos.

#### Scenario: Gate permite rendir con perfil completo
- **WHEN** `puedeRendir()` retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate bloquea el examen con perfil incompleto
- **WHEN** `puedeRendir()` retorna `{ puede: false, razon: string }`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra un mensaje con la razón del bloqueo y un enlace a `/alumno/perfil`

