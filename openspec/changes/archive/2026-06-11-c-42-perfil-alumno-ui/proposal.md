## Why

`StudentProfile.tsx` tiene 700+ líneas con toda la vista del perfil (`paso==='perfil'`) inline: avatar, datos personales, banners de estado, y cuatro secciones de requisitos (consentimiento, biometría, foto, DNI) con lógica de presentación entrelazada. El resultado es una pantalla difícil de leer, mantener y escanear visualmente — el alumno no puede entender de un vistazo qué falta para completar su perfil. C-42 extrae la vista del perfil en componentes de presentación pura y le da un look minimalista uniforme, sin tocar la máquina de fases ni el gate de `perfil_completo`.

## What Changes

- **Nuevo componente `PerfilHeaderCard`** — encabezado de perfil con avatar condicional (foto circular si existe, inicial si no — lógica ya presente en C-37) + datos personales (nombre, legajo, email, institución, jurisdicción). Encapsula el bloque `flex items-center` + grid de datos que hoy vive inline en `StudentProfile`.
- **Nuevo componente `RequisitoCard`** — tarjeta genérica y reutilizable para un requisito de enrollment: recibe `icon`, `title`, `badge` (tono + label), `children` (detalle), `action` (botón CTA opcional). Un patrón único para los cuatro requisitos: consentimiento, biometría, foto, DNI. DRY sobre los cuatro `<Card className="space-y-md">` actuales.
- **Nuevo componente `PerfilBannerEstado`** — banner contextual de estado del perfil: `perfilCompleto`, `caducada`, `renovacionRequerida`. Encapsula los tres banners condicionales que hoy preceden las secciones.
- **Refactor de `StudentProfile` vista `paso==='perfil'`** — usa los tres componentes nuevos; queda como orquestador delgado (handlers + estado). Todas las props se pasan hacia abajo; la lógica de fases, el gate, la navegación y los handlers quedan intactos en `StudentProfile`.
- **Delta spec de `student-profile-shell`** — actualiza el requisito de presentación para documentar los componentes y el look minimalista con tarjetas uniformes.
- **Nueva spec `profile-requisito-cards`** — documenta el patrón `RequisitoCard` y los cuatro usos concretos (consentimiento, biometría, foto, DNI).

## Capabilities

### New Capabilities

- `profile-requisito-cards`: Componente `RequisitoCard` y sus cuatro instancias (`ConsentimientoCard`, `BiometriaCard`, `FotoCard`, `DniCard`) como wrappers de presentación que usan `RequisitoCard`. Cubre el patrón visual de tarjeta de requisito con badge de estado y CTA opcional.
- `profile-header-card`: Componente `PerfilHeaderCard` — encabezado del perfil con avatar condicional y datos personales del alumno.
- `profile-banner-estado`: Componente `PerfilBannerEstado` — banners contextuales (perfil completo, caducado, renovación requerida).

### Modified Capabilities

- `student-profile-shell`: La vista principal del perfil (`paso==='perfil'`) pasa a estar componentizada. Los requisitos de presentación cambian: cada sección de requisito es ahora una `RequisitoCard` uniforme; el encabezado es `PerfilHeaderCard`; los banners son `PerfilBannerEstado`. El comportamiento funcional (gate `perfil_completo`, lógica de fases, handlers) no cambia.

## Impact

- **Archivos modificados**: `frontend/src/screens/StudentProfile.tsx` (vista `paso==='perfil'` se simplifica, se mantienen handlers y lógica de fases)
- **Archivos nuevos**: `frontend/src/screens/alumno/components/PerfilHeaderCard.tsx`, `frontend/src/screens/alumno/components/RequisitoCard.tsx`, `frontend/src/screens/alumno/components/PerfilBannerEstado.tsx`, y cuatro wrappers opcionales: `ConsentimientoCard.tsx`, `BiometriaCard.tsx`, `FotoCard.tsx`, `DniCard.tsx`
- **Specs**: nueva spec `profile-requisito-cards`, nueva spec `profile-header-card`, nueva spec `profile-banner-estado`, delta en `student-profile-shell`
- **Sin impacto en**: máquina de fases `PasoEnrollment`, handlers (`handleConsentido`, `handleFotoCapturada`, `handleBiometriaCapturada`, `handleDniEscaneado`, `handleRenovarBiometria`), gate `perfil_completo`, `DEV_TOOLS_ENABLED` block (queda en `StudentProfile`)
- **Sin impacto en**: `EnrollmentConsentStep`, `EnrollmentBiometricStep`, `EnrollmentDniStep`, `CameraSnapshotCapture`, `BiometricRenewalStatus` — componentes de pasos ya extraídos en changes anteriores
- **Dependencias de UI**: `Card`, `Badge`, `Button`, `Icon` de `ui/components.tsx`; `Term` de `ui/Term.tsx`; `BiometricRenewalStatus` (reutilizado dentro de `BiometriaCard`)
