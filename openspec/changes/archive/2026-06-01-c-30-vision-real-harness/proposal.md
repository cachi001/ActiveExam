## Why

El harness de diagnóstico admin (`/admin/detection-test`) opera hoy con señales completamente simuladas: el motor `MediaPipeVisionEngine` es un stub que tira error en todos sus métodos, y el harness lo captura silenciosamente devolviendo `face_count: 1` hardcodeado (líneas 469–487 de `AdminDetectionHarness.tsx`). Esto significa que el admin nunca puede verificar que la cámara y los detectores funcionan en su entorno real, el `face_count` siempre muestra "1" aunque haya 0 o 3 personas frente a la cámara, y no existe feedback visual de lo que MediaPipe está detectando. C-30 cablea `@mediapipe/tasks-vision` **ÚNICAMENTE en el harness**, dejando intacto el flujo de examen (que sigue con señales simuladas), y dibuja un overlay de landmarks y bounding boxes sobre el video para que el admin vea exactamente qué detecta la cámara.

## What Changes

- **Motor real MediaPipe solo en el harness**: se completa la implementación de `MediaPipeVisionEngine` (o se crea `RealMediaPipeVisionEngine`) con `@mediapipe/tasks-vision` Tasks API para los tres detectores: `FaceDetector`, `FaceLandmarker` (468 landmarks + iris), `PoseLandmarker`. Cargado con **import dinámico (lazy)** únicamente en la ruta `/admin/detection-test` — el bundle principal NO cambia.
- **Modelos servidos localmente**: los binarios `.wasm` y los archivos de modelo `.task` de MediaPipe se sirven desde `frontend/public/mediapipe/` (nunca desde CDN externo). Se documenta el script de descarga / instrucción de copiado. Requerimiento de soberanía de datos y self-hosted.
- **Overlay canvas sobre el video**: un `<canvas>` superpuesto al `<video>` dibuja en tiempo real: bounding boxes de cada rostro detectado, puntos clave del Face Mesh (o subconjunto legible), y opcionalmente keypoints de pose. El admin puede ver qué captura la cámara frame a frame.
- **Actualización del banner de C-29**: el banner "SEÑALES DE VISIÓN SIMULADAS" se vuelve condicional. Cuando el motor real está activo y los modelos cargaron con éxito, el banner pasa a "VISIÓN REAL (MediaPipe)". Si el motor no pudo cargar (WebGL ausente, modelo no encontrado), el banner indica claramente el error y el harness NO cae a simulación silenciosa.
- **Fallback honesto**: si `@mediapipe/tasks-vision` no puede inicializar (WebGL no disponible, archivo `.task` no encontrado, timeout de carga), se muestra un error explícito en la UI. No se simula como si fuera real.
- **Sin cambios en el flujo de examen**: `Examen.tsx`, `VisionPipeline`, `StateTransitionRules`, `StudentEventChannel` y todo el flujo de producción siguen exactamente igual. El motor real opera exclusivamente dentro del contexto del harness.

## Capabilities

### New Capabilities

- `real-vision-engine-harness`: Implementación concreta de `VisionEngine` con `@mediapipe/tasks-vision` Tasks API (FaceDetector + FaceLandmarker + PoseLandmarker), cargada de forma lazy y con modelos locales. Solo instanciada en el harness de diagnóstico admin. Incluye lógica de inicialización, fallback de error y dispose.
- `vision-overlay-canvas`: Componente `<VisionOverlay>` (o función de render sobre canvas) que dibuja en tiempo real sobre el feed de video: bounding boxes de rostros detectados, puntos clave del Face Mesh, keypoints de pose (cuando disponible). Parámetros configurables (colores, densidad de landmarks).
- `harness-model-loader`: Módulo que resuelve la carga de modelos `.task` desde rutas locales (`/mediapipe/*.task`), gestiona el estado de carga (loading / loaded / error), expone progreso, y documenta cómo obtener los modelos (instrucción de descarga a `public/mediapipe/`).

### Modified Capabilities

- `harness-legibility-layer` (C-29): el banner de simulación deja de ser estático y pasa a ser condicional según el estado real del motor (simulado / cargando / real-activo / error). La capacidad de comunicar honestamente el estado del motor es un DELTA de comportamiento de esta capability.
- `admin-detection-test-harness` (C-23): el harness abandona el fallback a señales hardcodeadas para visión y pasa a recibir señales reales del `RealMediaPipeVisionEngine`. El catch de "motor no cableado" se reemplaza por propagación del error real.

## Impact

- **Archivos nuevos**: `frontend/src/vision/RealMediaPipeVisionEngine.ts` (o completar `MediaPipeVisionEngine.ts`), `frontend/src/vision/harnessEngineLoader.ts`, `frontend/src/ui/VisionOverlay.tsx`, script de descarga de modelos (`scripts/download-mediapipe-models.sh` o `.ps1`).
- **Archivos modificados**: `frontend/src/screens/AdminDetectionHarness.tsx` (instanciar motor real, cablear overlay, actualizar banner), `frontend/src/config/glossary.ts` (términos nuevos si aplica).
- **Directorio nuevo**: `frontend/public/mediapipe/` (modelos `.task` + binarios WASM — ignorados en `.gitignore` si superan el límite de repo, con instrucción de descarga).
- **Dependencia nueva en `package.json`**: `@mediapipe/tasks-vision` (cargado solo en el chunk del harness por lazy import).
- **Sin cambios en**: `VisionEngine.ts` (interfaz abstracta intacta), `VisionPipeline.ts`, `stateTransitionRules.ts`, `Examen.tsx`, `StudentEventChannel.ts`, ni ningún otro archivo del flujo de examen.
- **Bundle**: el chunk principal NO debe incluir `@mediapipe/tasks-vision`. Solo el chunk lazy del harness.
