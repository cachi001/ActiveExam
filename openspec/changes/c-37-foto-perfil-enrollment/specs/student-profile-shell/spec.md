## MODIFIED Requirements

### Requirement: La pantalla de perfil muestra los datos personales del alumno
El sistema SHALL proveer la pantalla `/alumno/perfil` que muestre el nombre completo, legajo, email institucional y la institución (`UTN Regional Mendoza`) del alumno autenticado. El encabezado de datos personales SHALL mostrar un avatar circular: si `principal.foto_perfil` contiene un dataURL, SHALL mostrar `<img>` circular con esa imagen; si no, SHALL mostrar la inicial del nombre en un contenedor circular de fondo `secondary-container`.

#### Scenario: Datos personales visibles en el perfil
- **WHEN** el alumno navega a `/alumno/perfil`
- **THEN** se muestran: nombre completo, legajo (`id_institucional`), email (`@frm.utn.edu.ar`) e institución

#### Scenario: Email del perfil es de UTN FRM
- **WHEN** el alumno autenticado es el principal de demo para rol `estudiante`
- **THEN** el email mostrado en el perfil termina en `@frm.utn.edu.ar`

#### Scenario: Avatar con foto de perfil capturada
- **WHEN** `principal.foto_perfil` contiene un dataURL JPEG válido
- **THEN** el encabezado de datos personales muestra `<img>` circular con la foto del alumno en lugar de la inicial

#### Scenario: Avatar con inicial cuando no hay foto de perfil
- **WHEN** `principal.foto_perfil` es `undefined`
- **THEN** el encabezado de datos personales muestra la inicial del nombre en el contenedor circular (comportamiento previo)

### Requirement: El perfil incluye el paso foto_perfil en el flujo de enrollment entre consentimiento y biometría
El sistema SHALL mostrar el paso `'foto_perfil'` en el flujo de enrollment de `StudentProfile.tsx`. El paso SHALL renderizar el componente `CameraSnapshotCapture` con `shape='oval'` y la instrucción "Posicioná tu cara dentro del óvalo". El encabezado del paso SHALL mostrar "Foto de perfil" y el contador de pasos actualizado (Paso 2 de N). Al completar o cancelar el paso SHALL navegar a `'biometria'`. El paso SHALL incluir una nota de privacidad (Ley 25.326) visible en el encabezado del paso.

#### Scenario: Paso foto_perfil muestra CameraSnapshotCapture oval
- **WHEN** el enrollment está en paso `'foto_perfil'`
- **THEN** se renderiza `CameraSnapshotCapture` con `shape='oval'` dentro del `StudentShell`

#### Scenario: Encabezado del paso foto_perfil muestra título y contador
- **WHEN** el enrollment está en paso `'foto_perfil'`
- **THEN** el encabezado muestra "Foto de perfil" y el texto del contador (e.g., "Paso 2 de 3")

#### Scenario: Nota de privacidad visible en el paso foto_perfil
- **WHEN** el enrollment está en paso `'foto_perfil'`
- **THEN** se muestra texto indicando que la foto es un dato personal (Ley 25.326), con finalidad acotada y eliminación al egreso

## ADDED Requirements

### Requirement: La StaffShell muestra avatar circular condicional en el footer del sidebar
El sistema SHALL actualizar el footer del sidebar de `StaffShell` en `shells.tsx` para mostrar la foto de perfil del principal como avatar circular si `principal.foto_perfil` está definido; de lo contrario SHALL mostrar la inicial actual. El cambio aplica al elemento `div.w-9.h-9.rounded-full` de la línea ~97.

#### Scenario: StaffShell sidebar — avatar con foto
- **WHEN** `principal.foto_perfil` contiene un dataURL JPEG
- **THEN** el footer del sidebar de StaffShell muestra `<img className="w-9 h-9 rounded-full object-cover" src={principal.foto_perfil} />`

#### Scenario: StaffShell sidebar — avatar con inicial (sin foto)
- **WHEN** `principal.foto_perfil` es `undefined`
- **THEN** el footer del sidebar de StaffShell muestra la inicial del nombre (comportamiento existente)
