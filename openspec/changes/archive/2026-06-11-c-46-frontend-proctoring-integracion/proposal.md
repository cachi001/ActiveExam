## Why

El backend slim de proctoring (C-45) existe pero el frontend no lo usa: el harness diagnóstico (`AdminDetectionHarness`) opera completamente aislado (LocalHarnessEventSink, sin red), la verificación biométrica no tiene destino de persistencia, y la vista de revisión (`Revisor`/`SessionDetail`) trabaja sobre datos mock. El flujo completo **detectar → grabar → revisar** nunca cierra en el sistema real: las sesiones grabables no existen, los screenshots quedan solo en vivo (no persisten) y el revisor no puede ver la historia completa de eventos con sus capturas y veredictos de re-inferencia. Esto imposibilita validar el pipeline E2E antes de un examen real.

## What Changes

- **`api.ts`**: agregar cinco métodos duales (`crearSesionProctoring`, `enviarEventoProctoring`, `enviarBiometriaProctoring`, `listarSesionesProctoring`, `getSesionProctoring`) con fallback mock completo cuando `USE_REAL_BACKEND=0` — el sitio sigue funcionando en Vercel sin backend.
- **Tipos de proctoring**: nuevos tipos TypeScript en `types.ts` calcados del backend C-45 (`SesionProctoringResumen`, `SesionProctoringDetalle`, `EventoProctoringDetalle`, `BiometriaDetalle`, `VeredictoReinferencia`).
- **`AdminDetectionHarness`**: modo "Grabar sesión" — botón toggle que crea una sesión en el backend, captura un screenshot por cada evento (frame del `<video>` a canvas → base64) y lo envía con el evento al backend; muestra estado "grabando" + contador; errores de red no rompen el diagnóstico (degradación local).
- **Helper de screenshot**: función `captureVideoFrame(videoEl, jpegQuality)` → `string | null` — reutiliza el patrón de `CameraSnapshotCapture` (canvas + toDataURL) sin importar el componente completo.
- **Biometría → backend**: al completar la verificación biométrica, POST al endpoint `/sessions/{id}/biometria` de la sesión activa de proctoring, atado por `sessionId` de contexto.
- **Vista de revisión real** (`ProctoringRevisor`): lista de sesiones (GET /sessions) + detalle (GET /sessions/{id}) con cada evento + su screenshot + veredicto de re-inferencia + face_count cliente/servidor + biometría + score. Reutiliza `Card`, `Badge`, `SeverityBadge`, `SectionTitle`, `ReviewQueueItem` (patrón C-43). Decisión humana explícita (L2.5).
- **Mejora de umbrales de detección** en `stateTransitionRules.ts`: ajuste fino de `DEFAULT_CONFIG` para reducir falsos positivos (mirada, rostro ausente) basado en observaciones del harness.

## Capabilities

### New Capabilities
- `proctoring-api-client`: métodos duales real/mock para las cinco operaciones REST del backend C-45; tipos TypeScript de proctoring (sesión, evento, biometría, veredicto).
- `harness-record-mode`: modo "Grabar sesión" en el harness diagnóstico — crea sesión, captura screenshots por evento, envía al backend, estado grabando + contador, degradación a local si la red falla.
- `video-frame-capture`: helper puro `captureVideoFrame(videoEl, quality)` que extrae el frame actual del `<video>` como base64 JPEG; reutilizable en otros contextos.
- `proctoring-revisor-real`: vista de revisión real de sesiones persistidas — lista + detalle con screenshots, veredictos de re-inferencia, comparación face_count cliente/servidor, biometría y score; decisión humana L2.5.

### Modified Capabilities
- `admin-detection-test-harness`: agrega modo "Grabar sesión" como extensión opcional (el modo diagnóstico puro sin red se preserva intacto).
- `state-transition-rules`: ajuste fino de `DEFAULT_CONFIG` (umbrales de mirada y rostro ausente) para reducir falsos positivos observados con el motor MediaPipe real.

## Impact

- **Archivos modificados**: `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/screens/AdminDetectionHarness.tsx`, `frontend/src/proctoring/stateTransitionRules.ts`
- **Archivos nuevos**: `frontend/src/lib/videoFrameCapture.ts`, `frontend/src/screens/ProctoringRevisor.tsx`, `frontend/src/screens/ProctoringSessionDetail.tsx`
- **Dependencia**: backend C-45 (`POST /sessions`, `/events`, `/biometria`, `GET /sessions`, `GET /sessions/{id}`) corriendo en Railway; sin `USE_REAL_BACKEND=1` todo opera en mock.
- **Datos sensibles (Ley 25.326)**: los screenshots se tratan como dato sensible; se transmiten solo hacia el backend slim ya configurado para ello; en mock no se almacenan imágenes reales.
- **L2.5**: la vista de revisión nunca sanciona automáticamente; el score es un acumulador de priorización; la decisión disciplinaria es siempre humana.
