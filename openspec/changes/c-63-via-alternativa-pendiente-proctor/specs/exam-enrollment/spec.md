## MODIFIED Requirements

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL evaluar `api.puedeRendir()` antes de permitir el inicio del flujo de examen. Si el resultado es `{ puede: false }`, el sistema SHALL mostrar el motivo específico al alumno según el código retornado. El código `via_alternativa_pendiente` SHALL mostrar el mensaje "Tu verificación alternativa está pendiente de aprobación de un proctor" con indicación de que no debe intentar rendir. El código `via_alternativa_habilitada` (proveniente de habilitación por proctor) SHALL permitir rendir sin biometría. Si el resultado es `{ puede: false }` por cualquier otro motivo, el sistema SHALL redirigir al alumno a `/alumno/perfil`.

#### Scenario: Gate permite rendir con perfil completo
- **WHEN** `puedeRendir()` retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate bloquea el examen con perfil incompleto genérico
- **WHEN** `puedeRendir()` retorna `{ puede: false, razon: string }` con código distinto de `via_alternativa_pendiente`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra un mensaje con la razón del bloqueo y un enlace a `/alumno/perfil`

#### Scenario: Gate bloquea con vía alternativa pendiente de habilitación
- **WHEN** `puedeRendir()` retorna `{ puede: false, codigo: "via_alternativa_pendiente" }`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra el mensaje "Tu verificación alternativa está pendiente de aprobación de un proctor."
- **THEN** el botón "Rendir" aparece deshabilitado con el motivo visible
- **THEN** NO se muestra el enlace a `/alumno/perfil` (el perfil ya tiene la solicitud registrada)

#### Scenario: Gate permite rendir con vía alternativa habilitada por proctor
- **WHEN** `puedeRendir()` retorna `{ puede: true }` para un alumno con `habilitado_por_proctor`
- **THEN** el flujo navega a `/requisitos` omitiendo el paso de biometría
- **THEN** el sistema no exige captura biométrica al alumno durante el examen

### Requirement: La pantalla "Mis exámenes" muestra el registro de inscripciones
El sistema SHALL proveer la pantalla `/alumno/mis-examenes` que liste todas las inscripciones del alumno con su estado y la acción siguiente disponible. El estado SHALL ser uno de: `inscripto`, `pendiente`, `habilitado`, `rendido`. Cuando el alumno tiene una solicitud de vía alternativa con estado `pendiente_proctor`, la pantalla SHALL mostrar un badge "Verificación alternativa pendiente" asociado a la inscripción correspondiente y el botón "Rendir" SHALL aparecer deshabilitado con el tooltip o texto "Pendiente de habilitación por proctor".

#### Scenario: Lista de inscripciones visible
- **WHEN** el alumno navega a `/alumno/mis-examenes`
- **THEN** se renderiza la lista de inscripciones retornada por `api.misInscripciones()`

#### Scenario: Inscripción con estado "habilitado" y perfil completo muestra acción "Rendir"
- **WHEN** una inscripción tiene estado `habilitado` y `puedeRendir().puede` es `true`
- **THEN** se muestra el botón "Rendir" que navega al flujo existente iniciando en `/requisitos`

#### Scenario: Inscripción con estado "habilitado" y perfil incompleto muestra acción "Completar perfil"
- **WHEN** una inscripción tiene estado `habilitado` y `puedeRendir().puede` es `false` con código distinto de `via_alternativa_pendiente`
- **THEN** se muestra el botón "Completar perfil" que navega a `/alumno/perfil`
- **THEN** no se muestra el botón "Rendir"

#### Scenario: Inscripción con vía alternativa pendiente muestra badge y botón deshabilitado
- **WHEN** el alumno tiene solicitud de vía alternativa con estado `pendiente_proctor` para esa inscripción
- **THEN** se muestra el badge "Verificación alternativa pendiente" junto a la inscripción
- **THEN** el botón "Rendir" se muestra deshabilitado con texto explicativo "Pendiente de habilitación por proctor"
- **THEN** NO se muestra el botón "Completar perfil"

#### Scenario: Inscripción con estado "rendido" muestra resultado
- **WHEN** una inscripción tiene estado `rendido`
- **THEN** se muestra el badge "Rendido" sin botón de acción primaria

#### Scenario: Lista vacía muestra mensaje de ayuda
- **WHEN** el alumno no tiene inscripciones registradas
- **THEN** la pantalla muestra un mensaje invitando a inscribirse en `/alumno/materias`

### Requirement: BiometricCapture notifica al caller con resultado biométrico completo
El componente `BiometricCapture` SHALL invocar el callback `onComplete` con la firma ampliada: `(landmarks: FaceLandmark[], frame: HTMLCanvasElement | null, passiveOk: boolean, retosResueltos: string[], virtualCameraDetected: boolean)`. Los callers del componente (verificación en `Biometria.tsx` y enrollment en el perfil del alumno) SHALL actualizar su handler para aceptar los nuevos parámetros. Este requirement no se modifica en este change — se preserva íntegro para no perder el contrato establecido.

#### Scenario: onComplete invocado con todos los parámetros reales
- **WHEN** el alumno completa todos los retos activos y el liveness pasivo tiene resultado
- **THEN** `onComplete` se invoca con `landmarks` del último frame, `frame` del canvas, `passiveOk` calculado, `retosResueltos` del `resueltosRef` y `virtualCameraDetected` del detector
- **THEN** el handler de `Biometria.tsx` recibe todos los parámetros sin errores TypeScript

#### Scenario: onComplete en modo fallback manual
- **WHEN** el motor falla y el alumno completa los retos en modo manual
- **THEN** `onComplete` se invoca con `passiveOk: false`, `retosResueltos` de los retos marcados manualmente, `virtualCameraDetected: false`
- **THEN** `landmarks` puede ser vacío (`[]`) si no hubo detección

#### Scenario: Caller de enrollment actualizado
- **WHEN** `BiometricCapture` se monta para el flujo de enrollment en el perfil del alumno
- **THEN** el handler `onComplete` del caller de enrollment acepta los 5 parámetros sin error de compilación TypeScript
- **THEN** el flujo de enrollment no se interrumpe aunque ignore `passiveOk` / `virtualCameraDetected`
