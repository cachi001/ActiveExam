# student-profile-shell Specification

## Purpose
TBD - created by archiving change c-21-portal-alumno-materias-inscripcion. Update Purpose after archive.
## Requirements
### Requirement: La pantalla de perfil muestra los datos personales del alumno
El sistema SHALL proveer la pantalla `/alumno/perfil` que muestre el nombre completo, legajo, email institucional y la institución (`UTN Regional Mendoza`) del alumno autenticado.

#### Scenario: Datos personales visibles en el perfil
- **WHEN** el alumno navega a `/alumno/perfil`
- **THEN** se muestran: nombre completo, legajo (`id_institucional`), email (`@frm.utn.edu.ar`) e institución

#### Scenario: Email del perfil es de UTN FRM
- **WHEN** el alumno autenticado es el principal de demo para rol `estudiante`
- **THEN** el email mostrado en el perfil termina en `@frm.utn.edu.ar`

### Requirement: El perfil incluye contenedores de consentimiento y biometría con estado de completitud
El sistema SHALL mostrar dos secciones en el perfil: "Consentimiento informado" y "Verificación biométrica". Cada sección SHALL indicar visualmente si está completada (`completado`) o pendiente (`pendiente`).

#### Scenario: Sección de consentimiento muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión demo
- **THEN** la sección "Consentimiento informado" muestra estado `pendiente`

#### Scenario: Sección de biometría muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión demo
- **THEN** la sección "Verificación biométrica" muestra estado `pendiente`

#### Scenario: Perfil completo habilita el gate puedeRendir
- **WHEN** ambas secciones (consentimiento y biometría) están en estado `completado`
- **THEN** `api.puedeRendir()` retorna `{ puede: true }`

#### Scenario: Perfil incompleto mantiene el gate bloqueado
- **WHEN** al menos una sección (consentimiento o biometría) está en estado `pendiente`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: string }` describiendo qué falta completar

### Requirement: Las secciones de contenido real son placeholders en C-21
El sistema SHALL dejar como contenedor vacío (placeholder) el contenido de las secciones "Consentimiento informado" y "Verificación biométrica". El contenido real (texto de consentimiento, captura de foto biométrica) SHALL ser implementado por C-22. El placeholder SHALL indicar explícitamente que el contenido está pendiente de implementación.

#### Scenario: Placeholder visible cuando sección está pendiente
- **WHEN** una sección de perfil está en estado `pendiente` y el alumno la expande
- **THEN** se muestra un mensaje indicando que el contenido estará disponible próximamente (placeholder de C-22)
- **THEN** no se renderiza ningún formulario ni captura real de datos

### Requirement: El paso biométrico del perfil delega la captura a BiometricCapture
El sistema SHALL refactorizar `EnrollmentBiometricStep` para que la captura de referencia biométrica use el componente `BiometricCapture` en lugar de implementar su propio loop RAF, manejo de motor y UI de retos. `EnrollmentBiometricStep` SHALL mantener: el encabezado contextual (renovación, nota de privacidad Ley 25.326), la fase `instrucciones` con el botón "Iniciar captura de referencia", y el callback `onCapturada`. Los elementos eliminados de `EnrollmentBiometricStep` SHALL incluir: `startDetectionLoop`, `resolverRetoFromLoop`, `resolverRetoManual`, `activarFullscreen`, `salirFullscreen`, `engineRef`, `challengeCountsRef`, `lastLandmarksRef`, `rafHandleRef`, y toda la UI inline de retos con botones.

#### Scenario: La fase capturando de EnrollmentBiometricStep muestra BiometricCapture
- **WHEN** el alumno hace clic en "Iniciar captura de referencia" en el perfil
- **THEN** `EnrollmentBiometricStep` pasa a fase `capturando`
- **THEN** renderiza `<BiometricCapture onComplete={handleComplete} onCancel={cancelarCaptura} />`
- **THEN** la UI inmersiva del overlay es gestionada por `BiometricCapture`

#### Scenario: handleComplete en el perfil calcula embedding y guarda referencia
- **WHEN** `BiometricCapture` llama `onComplete(landmarks)` en el contexto del perfil
- **THEN** `EnrollmentBiometricStep` calcula el embedding con `embeddingFromLandmarks(landmarks)`
- **THEN** captura el frame del video para la imagen de referencia (si disponible)
- **THEN** llama `api.guardarReferenciaBiometrica({ imagen, embedding })` y pasa a fase `completado`
- **THEN** llama el callback `onCapturada(referencia)`

#### Scenario: Cancelar en BiometricCapture vuelve a instrucciones en el perfil
- **WHEN** `BiometricCapture` llama `onCancel()` en el contexto del perfil
- **THEN** `EnrollmentBiometricStep` vuelve a la fase `instrucciones`

#### Scenario: El encabezado y la nota de privacidad permanecen fuera del overlay
- **WHEN** la fase es `instrucciones` o `completado` o `error`
- **THEN** el encabezado contextual (renovación, datos biométricos, vigencia) y la nota de privacidad Ley 25.326 son visibles
- **WHEN** la fase es `capturando` (overlay activo)
- **THEN** el encabezado y la nota de privacidad no se superponen con el overlay de `BiometricCapture`

