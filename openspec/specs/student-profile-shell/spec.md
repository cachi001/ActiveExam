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
El sistema SHALL mostrar dos secciones en el perfil: "Consentimiento informado" y "Verificación biométrica". Cada sección SHALL indicar visualmente si está completada (`completado`) o pendiente (`pendiente`). En modo demo, cada sección SHALL incluir un control "Demo: simular completado" para simular la completitud sin implementar el flujo real.

#### Scenario: Sección de consentimiento muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión demo
- **THEN** la sección "Consentimiento informado" muestra estado `pendiente`

#### Scenario: Sección de biometría muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión demo
- **THEN** la sección "Verificación biométrica" muestra estado `pendiente`

#### Scenario: Simular completitud de consentimiento en demo
- **WHEN** el alumno activa "Demo: simular completado" en la sección de consentimiento
- **THEN** la sección muestra estado `completado` y el indicador visual cambia a completado

#### Scenario: Simular completitud de biometría en demo
- **WHEN** el alumno activa "Demo: simular completado" en la sección de verificación biométrica
- **THEN** la sección muestra estado `completado` y el indicador visual cambia a completado

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

