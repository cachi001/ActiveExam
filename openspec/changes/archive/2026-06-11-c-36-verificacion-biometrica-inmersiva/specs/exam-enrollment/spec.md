## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: La pantalla /biometria usa detección real de liveness via BiometricCapture
El sistema SHALL reemplazar el mock de botones manuales en `Biometria.tsx` por el componente `BiometricCapture`. En la fase `capturando`, SHALL renderizar `<BiometricCapture onComplete={handleComplete} onCancel={handleCancel} />`. El handler `handleComplete(landmarks)` SHALL calcular el embedding con `embeddingFromLandmarks(landmarks)` y llamar al flujo de verificación server-side. Los botones de simulación manual (`onClick={() => resolver(d.id)}`) SHALL ser eliminados.

#### Scenario: Fase capturando muestra el overlay inmersivo con detección real
- **WHEN** el alumno inicia la verificación en `/biometria`
- **THEN** se renderiza el overlay `BiometricCapture` con UI inmersiva
- **THEN** no hay botones de simulación manual visibles
- **THEN** los retos se detectan automáticamente por el motor MediaPipe

#### Scenario: Al completar retos, el flujo continúa con verificar()
- **WHEN** `BiometricCapture` llama `onComplete(landmarks)` con los landmarks del último frame
- **THEN** `Biometria.tsx` calcula el embedding con `embeddingFromLandmarks(landmarks)`
- **THEN** pasa a la fase `verificando` y llama `api.verifyIdentity()`

#### Scenario: Al cancelar, vuelve a la fase preparar
- **WHEN** `BiometricCapture` llama `onCancel()`
- **THEN** `Biometria.tsx` vuelve a la fase `preparar`

#### Scenario: Las fases verificando, verificado y reintento no cambian
- **WHEN** la verificación server-side completa
- **THEN** el comportamiento de las fases `verificando`, `verificado` y `reintento` es idéntico al anterior (incluyendo navegación a `/sala-espera` en éxito)
