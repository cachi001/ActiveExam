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

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL verificar que el alumno tenga un registro `embedding_referencia` con `vigente = TRUE` en la base de datos (además de consentimiento válido) como condición para que `puedeRendir()` retorne `{ puede: true }`. La verificación SHALL ser server-side: el backend evaluará si existe la referencia biométrica persistida, no si existe en el store del cliente.

#### Scenario: Gate permite rendir con perfil completo incluyendo referencia biométrica persistida
- **WHEN** el alumno tiene consentimiento válido Y tiene un registro `embedding_referencia` con `vigente = TRUE` en la DB
- **THEN** `api.puedeRendir()` (que llama al backend) retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate bloquea el examen si falta referencia biométrica en backend
- **WHEN** el alumno tiene consentimiento válido PERO no tiene un registro `embedding_referencia` con `vigente = TRUE` en la DB
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** el sistema no navega a `/requisitos`
- **THEN** se muestra un mensaje con la razón del bloqueo y un enlace a `/alumno/perfil` para completar el enrollment biométrico

#### Scenario: Gate bloquea si la referencia existe en localStorage pero no en backend
- **WHEN** el store Zustand o localStorage contiene un `referencia_id` pero el backend no tiene un registro `vigente = TRUE` para ese `usuario_id`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** la verificación es server-side y no puede ser bypasseada por manipulación del store local

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

### Requirement: La fase biometria del enrollment devuelve un referencia_id opaco al cliente
El sistema SHALL garantizar que al completar la fase `biometria` del enrollment, el cliente recibe únicamente el `referencia_id` (UUID opaco) del embedding persistido en el backend. El embedding crudo (array de floats) SHALL ser descartado del estado del cliente tras la confirmación del backend. El cliente SHALL tratar el `referencia_id` como un identificador de referencia para uso futuro (e.g., indicar qué referencia usar en la verificación de C-09), no como un dato biométrico.

#### Scenario: referencia_id almacenado en store tras enrollment exitoso
- **WHEN** `POST /api/v1/enrollment/embedding-referencia` retorna `{ referencia_id: "<uuid>" }` con HTTP 201
- **THEN** el store Zustand persiste `{ biometrico_referencia_id: "<uuid>" }` (u equivalente)
- **THEN** el embedding crudo es descartado de la memoria del cliente y de localStorage

#### Scenario: referencia_id visible como metadato en el perfil del alumno (UI)
- **WHEN** el alumno navega a `/alumno/perfil` y la sección de biometría está completada
- **THEN** la UI muestra el estado `completado` para la sección biométrica
- **THEN** la UI NO muestra el embedding crudo (ni parcialmente); puede mostrar el `referencia_id` truncado como referencia visual si el diseño lo requiere

