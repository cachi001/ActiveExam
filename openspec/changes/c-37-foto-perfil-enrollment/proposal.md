## Why

El alumno no tiene avatar real: hoy se muestra la inicial del nombre (un placeholder) en el encabezado del perfil (`StudentProfile.tsx:302-304`) y en la sidebar de staff (`shells.tsx:97-99`). La captura de foto de perfil no existe como paso del enrollment, lo que impide que el sistema asocie visualmente al alumno con su cuenta antes de llegar a la verificación biométrica de liveness. Agregarla como paso previo a la biometría completa el flujo de enrollment y permite que el avatar aparezca en toda la UI una vez capturado.

## What Changes

- Nuevo componente compartido **`CameraSnapshotCapture`** (`frontend/src/ui/CameraSnapshotCapture.tsx`): overlay inmersivo full-screen (estilo banco, fondo blanco, portal a `document.body`), `getUserMedia`, marco-guía parametrizable por forma (`shape: 'oval' | 'rect'`, con `aspectRatio` configurable para el rect del DNI), botón "Capturar" que toma snapshot vía canvas, preview con "Usar foto" / "Repetir", callbacks `onCapture(dataUrl)` / `onCancel()`. Texto/instrucción configurable por prop. Forma `'oval'` → foto de perfil; forma `'rect'` → DNI (reutilizable en C-38 sin tocar este componente).
- **`Principal.foto_perfil?: string`** — campo opcional (dataURL JPEG) agregado a la interfaz en `types.ts`.
- **`api.guardarFotoPerfil(dataUrl)`** — método mock: actualiza el principal en el store in-memory y retorna `ok`. Finalidad acotada, dato personal (Ley 25.326), eliminado al egreso.
- **Paso "Foto de perfil"** en el flujo de enrollment de `StudentProfile.tsx` — posicionado ANTES de `'biometria'`, DESPUÉS de `'consentimiento'`. La foto se captura con `CameraSnapshotCapture` forma `'oval'`. Al confirmar ("Usar foto"), se guarda vía `api.guardarFotoPerfil`. El paso NO bloquea el `perfil_completo` (que sigue siendo consentimiento + biometría vigente, sin cambio).
- **Avatar en la UI**: en `StudentProfile.tsx` (encabezado de datos personales) y en `shells.tsx` (`StaffShell` sidebar y `StudentShell` header info) → si `principal.foto_perfil` existe, `<img>` circular; si no, la inicial actual. **BREAKING** (comportamiento, no API): el avatar de StaffShell y el encabezado del StudentProfile pueden mostrar foto real cuando está disponible.
- Nuevo tipo de paso en `PasoEnrollment`: `'foto_perfil'`.

## Capabilities

### New Capabilities

- `camera-snapshot-capture`: componente compartido de captura de imagen fija con overlay inmersivo, marco-guía parametrizable (`oval` / `rect`) y flujo captura → preview → confirmar. Reutilizable por C-38 (DNI) sin modificación.
- `profile-photo-enrollment`: paso de captura de foto de perfil dentro del flujo de enrollment del alumno, con persistencia mock y visualización como avatar en la UI.

### Modified Capabilities

- `student-profile-shell`: agrega el nuevo paso `'foto_perfil'` a la máquina de fases del enrollment; modifica el encabezado de datos personales para mostrar la foto como avatar circular cuando está disponible; actualiza los contadores de pasos en el header de contexto ("Paso X de Y").
- `exam-enrollment`: el gate `puedeRendir` NO cambia; el paso de foto no es bloqueante. Sin cambio en los requisitos de habilitación.

## Impact

- **`frontend/src/ui/CameraSnapshotCapture.tsx`** — archivo nuevo (componente compartido).
- **`frontend/src/lib/types.ts`** — `Principal` +`foto_perfil?: string`.
- **`frontend/src/lib/api.ts`** — `guardarFotoPerfil(dataUrl)` mock; actualiza `PRINCIPALES.estudiante.foto_perfil` y propaga al store.
- **`frontend/src/screens/StudentProfile.tsx`** — nuevo paso `'foto_perfil'` en `PasoEnrollment`; handler `handleFotoCapturada`; lógica de navegación en `handleConsentido` y `handleIniciarEnrollment`; encabezado de datos personales con avatar condicional; contador de pasos actualizado.
- **`frontend/src/ui/shells.tsx`** — avatar en `StaffShell` sidebar (línea ~97) condicional a `principal.foto_perfil`; ídem en el bloque de datos del `StudentShell` header si aplica.
- No hay dependencias de npm nuevas — `getUserMedia` + `canvas.toDataURL` son APIs nativas del navegador.
- No requiere MediaPipe ni análisis de visión; la cámara se usa solo para snapshot estático.
- Ley 25.326: la foto de perfil es dato personal (no biométrico en sentido estricto); su tratamiento sigue las mismas reglas de finalidad acotada y eliminación al egreso que la imagen de referencia biométrica. En producción sería cifrada at-rest server-side; en demo es dataURL en memoria.
