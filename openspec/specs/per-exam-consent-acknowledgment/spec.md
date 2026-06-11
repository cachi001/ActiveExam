# per-exam-consent-acknowledgment Specification

## Purpose
TBD - created by archiving change c-26-acuse-consentimiento-por-examen. Update Purpose after archive.
## Requirements
### Requirement: El alumno otorga un acuse específico por examen antes de quedar habilitado para rendirlo
El sistema SHALL presentar, al inscribirse a un examen concreto, un paso de acuse por-examen que muestre el examen específico (cátedra, fecha/hora, duración) y el alcance de monitoreo de ESA instancia (cámara, pantalla/foco, pestañas), y SHALL exigir una acción afirmativa explícita del alumno para confirmar ESA instancia de tratamiento. El acuse por-examen NO SHALL re-capturar la biometría ni re-presentar el texto pesado del consentimiento de perfil: SHALL referenciar el acuse de perfil ya otorgado (C-22).

#### Scenario: El paso de acuse muestra el examen específico y el alcance de monitoreo
- **WHEN** el alumno inicia la inscripción a un examen concreto
- **THEN** el sistema muestra la cátedra, la fecha/hora y la duración de ese examen
- **THEN** el sistema muestra qué se va a monitorear (cámara, pantalla/foco, pestañas)

#### Scenario: El acuse referencia el consentimiento de perfil sin repetirlo
- **WHEN** se presenta el paso de acuse por-examen
- **THEN** el sistema indica que el consentimiento de perfil está vigente y enlaza al perfil
- **THEN** el sistema no inicia captura biométrica ni vuelve a presentar el texto pesado del consentimiento de perfil

#### Scenario: Acción afirmativa explícita sin casilla premarcada
- **WHEN** el alumno no realiza la acción afirmativa para confirmar la instancia
- **THEN** el sistema no registra el acuse por-examen
- **THEN** el examen no queda habilitado para rendir y el alumno no es sancionado

### Requirement: El sistema registra un acuse inmutable por (estudiante, examen)
El sistema SHALL registrar, ante una confirmación afirmativa, un acuse por-examen inmutable que incluya la versión del texto por-examen, un timestamp y un hash (simulado en la demo, sellado server-side en producción). El registro SHALL ser idempotente por par `(estudiante, examen)`: una segunda confirmación afirmativa para el mismo examen SHALL retornar el acuse existente sin crear un duplicado. El acuse por-examen NO SHALL constituir un nuevo tratamiento del dato biométrico.

#### Scenario: Registro de acuse afirmativo
- **WHEN** el alumno confirma afirmativamente el acuse de un examen vía `api.registrarAcuseExamen(examenId, { afirmativo: true })`
- **THEN** el sistema crea un `AcuseExamen` con `examen_id`, `version`, `timestamp` y `hash`
- **THEN** el acuse referencia el consentimiento de perfil vigente y no procesa biometría

#### Scenario: Acuse idempotente por examen
- **WHEN** ya existe un acuse afirmativo para ese `examen_id`
- **THEN** `api.registrarAcuseExamen(examenId, { afirmativo: true })` retorna el acuse existente sin crear un duplicado

#### Scenario: El acuse no se registra si el perfil de C-22 no está completo
- **WHEN** el alumno intenta acusar un examen pero su perfil de C-22 no está completo (consentimiento de perfil o biometría no vigentes)
- **THEN** el sistema no ofrece el acuse por-examen y deriva al alumno a completar el perfil

