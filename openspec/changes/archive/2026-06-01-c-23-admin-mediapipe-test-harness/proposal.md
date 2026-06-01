## Why

El pipeline de visión del cliente (C-11) — `VisionEngine` → `visionPipeline.onFrame` → `stateTransitionRules` → `EventSink` — está cableado exclusivamente en el flujo del alumno y no existe ninguna superficie de diagnóstico para que el equipo de desarrollo o el administrador verifique que los detectores MediaPipe (Face Detection, Face Mesh 468 landmarks, Pose) funcionan correctamente en el hardware objetivo ni que los eventos discretos producidos (tipo, severidad, payload) llegan correctamente al store y al canal de transporte (C-10). La ausencia de esta herramienta implica que los errores de calibración, umbrales o cableado solo se descubren durante una sesión real de examen.

## What Changes

- Nueva pantalla admin `AdminDetectionHarness` en `frontend/src/screens/` que instancia el mismo pipeline end-to-end (`MediaPipeVisionEngine` + `VisionPipeline` + `StateTransitionRules` + `EventSink` local) usando la cámara del propio administrador, sin examen activo ni sesión de alumno.
- La pantalla expone en vivo: señales crudas por frame (face_count, bounding boxes con confidence, gaze xy, pose keypoints disponibles), eventos discretos disparados (tipo, severidad, payload, trigger_evidence, ts_ms) y confirmación de que el `EventSink` los emitió/registró — camino `store.anomaliasVivo` / log local.
- Panel de configuración de umbrales (`TransitionConfig`) en tiempo real para ejercitar los thresholds sin reiniciar.
- Nueva ruta `/admin/detection-test` + entrada en `STAFF_NAV` (`ui/nav.ts`).
- No modifica ningún código de producción del flujo alumno; toda la lógica de visión y transporte se reutiliza sin duplicar.

## Capabilities

### New Capabilities

- `admin-detection-test-harness`: Pantalla admin que ejecuta el pipeline de visión completo (motor + reglas + sink) con la cámara del administrador y presenta señales crudas, eventos discretos y confirmación de registro — herramienta diagnóstica, sin examen real.
- `detection-event-verification`: Panel de verificación que confirma que cada evento emitido por `StateTransitionRules` llega al `EventSink` y se refleja en `store.anomaliasVivo`, con log ordenado, filtrable por severidad y exportable.

### Modified Capabilities

<!-- Sin cambios de requisitos en capabilities existentes. El pipeline de visión (C-11) y el transporte (C-10) se usan como dependencias sin modificar sus specs. -->

## Impact

- **Archivos nuevos**: `frontend/src/screens/AdminDetectionHarness.tsx`, spec files bajo `openspec/specs/admin-detection-test-harness/` y `openspec/specs/detection-event-verification/`.
- **Archivos modificados**: `frontend/src/ui/nav.ts` (nuevo ítem en `STAFF_NAV`), router de la app (nueva ruta `/admin/detection-test`).
- **Dependencias (solo lectura/uso)**: `frontend/src/vision/VisionEngine.ts`, `frontend/src/vision/MediaPipeVisionEngine.ts`, `frontend/src/proctoring/visionPipeline.ts`, `frontend/src/proctoring/stateTransitionRules.ts`, `frontend/src/lib/store.ts`.
- **Sin impacto en producción**: el harness es una pantalla admin protegida; no toca el flujo del alumno ni el backend.
