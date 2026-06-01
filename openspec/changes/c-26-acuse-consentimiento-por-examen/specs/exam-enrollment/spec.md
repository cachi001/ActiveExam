# Spec — exam-enrollment (delta C-26)

> La inscripción a un examen (de C-21) incorpora el paso de acuse por-examen; el gate `puedeRendir` evalúa además el acuse de ESE examen. Delta sobre la capability de C-21.

## MODIFIED Requirements

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL evaluar `api.puedeRendir(examenId)` antes de permitir el inicio del flujo de examen, evaluando un gate **en capas**: (1) perfil completo (consentimiento de perfil vigente o vía alternativa + biometría vigente, de C-22) **Y** (2) acuse por-examen presente y afirmativo para ESE `examenId`. Si el resultado es `{ puede: false }`, el sistema SHALL derivar al alumno al paso faltante —al perfil (`/alumno/perfil`) cuando falta (1), o al paso de acuse del examen cuando falta (2)— en lugar de iniciar el flujo de requisitos. El sistema NO SHALL sancionar ni bloquear silenciosamente: SHALL informar la razón y la acción siguiente.

#### Scenario: Gate permite rendir con perfil completo y acuse del examen
- **WHEN** `puedeRendir(examenId)` retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate deriva a perfil cuando el perfil está incompleto
- **WHEN** `puedeRendir(examenId)` retorna `{ puede: false }` con un código de perfil (`perfil_incompleto`, `consentimiento_version_desactualizada`, `biometria_caducada` o `biometria_renovacion_requerida`)
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra la razón y un enlace a `/alumno/perfil`

#### Scenario: Gate deriva al acuse cuando el perfil está completo pero falta el acuse del examen
- **WHEN** el perfil está completo pero no existe acuse afirmativo para ese examen y `puedeRendir(examenId)` retorna `{ puede: false, codigo: 'acuse_examen_faltante' }`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra la razón y la acción "Completar acuse del examen"

### Requirement: La pantalla "Mis exámenes" muestra el registro de inscripciones
El sistema SHALL proveer la pantalla `/alumno/mis-examenes` que liste todas las inscripciones del alumno con su estado y la acción siguiente disponible. El estado SHALL ser uno de: `inscripto`, `pendiente`, `habilitado`, `rendido`. La acción siguiente SHALL reflejar el gate en capas: cuando falta el acuse por-examen, la acción SHALL ser "Completar acuse del examen"; cuando el perfil está incompleto, "Completar perfil"; cuando el gate completo está satisfecho, "Rendir".

#### Scenario: Lista de inscripciones visible
- **WHEN** el alumno navega a `/alumno/mis-examenes`
- **THEN** se renderiza la lista de inscripciones retornada por `api.misInscripciones()`

#### Scenario: Inscripción habilitada con gate completo muestra acción "Rendir"
- **WHEN** una inscripción tiene estado `habilitado` y `puedeRendir(examenId).puede` es `true`
- **THEN** se muestra el botón "Rendir" que navega al flujo existente iniciando en `/requisitos`

#### Scenario: Inscripción habilitada con perfil incompleto muestra acción "Completar perfil"
- **WHEN** una inscripción tiene estado `habilitado`, el perfil está incompleto y `puedeRendir(examenId).puede` es `false`
- **THEN** se muestra el botón "Completar perfil" que navega a `/alumno/perfil`
- **THEN** no se muestra el botón "Rendir"

#### Scenario: Inscripción habilitada con perfil completo pero sin acuse muestra acción "Completar acuse del examen"
- **WHEN** una inscripción tiene estado `habilitado`, el perfil está completo y `puedeRendir(examenId)` retorna `{ puede: false, codigo: 'acuse_examen_faltante' }`
- **THEN** se muestra el botón "Completar acuse del examen" que navega al paso de acuse por-examen
- **THEN** no se muestra el botón "Rendir"

#### Scenario: Inscripción con estado "rendido" muestra resultado
- **WHEN** una inscripción tiene estado `rendido`
- **THEN** se muestra el badge "Rendido" sin botón de acción primaria

#### Scenario: Lista vacía muestra mensaje de ayuda
- **WHEN** el alumno no tiene inscripciones registradas
- **THEN** la pantalla muestra un mensaje invitando a inscribirse en `/alumno/materias`
