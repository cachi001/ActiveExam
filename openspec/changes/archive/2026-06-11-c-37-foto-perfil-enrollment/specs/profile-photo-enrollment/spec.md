## ADDED Requirements

### Requirement: El tipo Principal incluye el campo foto_perfil opcional
El sistema SHALL extender la interfaz `Principal` en `frontend/src/lib/types.ts` con el campo `foto_perfil?: string` que contiene un dataURL JPEG de la foto de perfil del alumno. El campo SHALL ser opcional (compatible con los principales existentes que no tienen foto). En producción el campo correspondería a una URL o referencia cifrada server-side; en demo es un dataURL en memoria.

#### Scenario: Principal sin foto — campo ausente
- **WHEN** el alumno no ha capturado foto de perfil
- **THEN** `principal.foto_perfil` es `undefined`

#### Scenario: Principal con foto — campo presente
- **WHEN** el alumno completó el paso de foto de perfil
- **THEN** `principal.foto_perfil` contiene el dataURL JPEG de la foto capturada

### Requirement: api.guardarFotoPerfil persiste la foto en el registro in-memory del principal
El sistema SHALL proveer el método `api.guardarFotoPerfil(dataUrl: string): Promise<void>` que guarde el dataURL JPEG en `PRINCIPALES.estudiante.foto_perfil` del registro in-memory de demo. El método SHALL simular latencia de red (~300 ms). El almacenamiento SHALL acotarse a la finalidad de mostrar el avatar del alumno (Ley 25.326: dato personal, finalidad acotada, eliminado al egreso en producción).

#### Scenario: Guardar foto de perfil — persiste en PRINCIPALES.estudiante
- **WHEN** se llama `api.guardarFotoPerfil(dataUrl)` con un dataURL JPEG válido
- **THEN** `PRINCIPALES.estudiante.foto_perfil` contiene el dataURL recibido

#### Scenario: Latencia simulada
- **WHEN** se llama `api.guardarFotoPerfil(dataUrl)`
- **THEN** la promesa resuelve tras ~300 ms (simulando latencia de red)

### Requirement: El store de Zustand expone la acción setFotoPerfil para actualizar el principal en tiempo real
El sistema SHALL agregar la acción `setFotoPerfil(dataUrl: string)` al store de Zustand (`frontend/src/lib/store.ts`) que actualice `principal.foto_perfil` en el estado global sin reemplazar el resto del objeto principal. Esto permite que el avatar se actualice reactivamente en todos los componentes suscriptos al store sin necesidad de un re-login.

#### Scenario: setFotoPerfil actualiza el avatar en la UI reactivamente
- **WHEN** se llama `store.setFotoPerfil(dataUrl)` desde el handler del paso de foto
- **THEN** todos los componentes que leen `useApp(s => s.principal)` reciben el principal actualizado con el nuevo `foto_perfil`

#### Scenario: setFotoPerfil con principal nulo no lanza error
- **WHEN** se llama `store.setFotoPerfil(dataUrl)` y el store no tiene principal autenticado
- **THEN** el estado no cambia y no se lanza ningún error

### Requirement: El paso foto_perfil aparece en el enrollment ANTES de la biometría y NO bloquea perfil_completo
El sistema SHALL agregar el paso `'foto_perfil'` al tipo `PasoEnrollment` de `StudentProfile.tsx`. El paso SHALL posicionarse después de `'consentimiento'` y antes de `'biometria'`. Al consentir sin vía alternativa y sin foto previa, el enrollment SHALL navegar a `'foto_perfil'`. Al capturar o cancelar el paso de foto, el enrollment SHALL navegar a `'biometria'`. El paso de foto SHALL ser sugerido pero NO obligatorio: si el alumno cancela `CameraSnapshotCapture` (sin foto), el enrollment continúa igualmente al paso `'biometria'`. La lógica de `recalcularPerfilCompleto` y el gate `puedeRendir` NO cambian.

#### Scenario: Flujo happy path — consentimiento → foto → biometría
- **WHEN** el alumno completa el consentimiento (sin vía alternativa) y no tiene foto previa
- **THEN** el enrollment navega al paso `'foto_perfil'`

#### Scenario: Captura de foto exitosa → continuar a biometría
- **WHEN** el alumno confirma la foto en `CameraSnapshotCapture` (llama `onCapture`)
- **THEN** el enrollment navega al paso `'biometria'`

#### Scenario: Cancelar la foto → continuar a biometría igualmente
- **WHEN** el alumno cancela `CameraSnapshotCapture` (llama `onCancel`)
- **THEN** el enrollment navega al paso `'biometria'` sin guardar foto

#### Scenario: Alumno con foto previa — saltar paso foto en re-enrollment
- **WHEN** el alumno ya tiene `principal.foto_perfil` definido y consiente nuevamente
- **THEN** el enrollment salta directamente a `'biometria'` (o a `'perfil'` si la biometría ya está vigente)

#### Scenario: Vía alternativa — sin paso de foto
- **WHEN** el alumno elige la vía alternativa (`via_alternativa=true`)
- **THEN** el enrollment navega a `'perfil'` directamente, sin pasar por `'foto_perfil'`

#### Scenario: gate puedeRendir no cambia por la foto
- **WHEN** el alumno tiene consentimiento vigente y biometría vigente pero NO tiene foto de perfil
- **THEN** `api.puedeRendir()` retorna `{ puede: true }` (la foto no bloquea el gate)
