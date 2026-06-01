## 1. Preparación del entorno — modelos y dependencia npm

- [x] 1.1 Agregar `@mediapipe/tasks-vision` a `frontend/package.json` con versión fijada (ej. `"@mediapipe/tasks-vision": "^0.10.14"`)
- [x] 1.2 Crear `frontend/public/mediapipe/.gitkeep` para que el directorio quede trackeado en git
- [x] 1.3 Agregar `frontend/public/mediapipe/*.task` y `frontend/public/mediapipe/*.wasm` a `.gitignore` del proyecto
- [x] 1.4 Crear `scripts/download-mediapipe-models.sh` con URLs versionadas de los tres modelos: `face_detector_short_range.task`, `face_landmarker.task`, `pose_landmarker_lite.task`
- [x] 1.5 Crear `scripts/download-mediapipe-models.ps1` (versión PowerShell equivalente para Windows)
- [x] 1.6 Verificar que los scripts imprimen el tamaño de cada archivo descargado y el directorio destino (`frontend/public/mediapipe/`)

## 2. RealMediaPipeVisionEngine — implementación del motor real

- [x] 2.1 Crear `frontend/src/vision/RealMediaPipeVisionEngine.ts` que implementa `VisionEngine` (el archivo NO importa `@mediapipe/tasks-vision` con import estático — debe quedar en un módulo separado que solo se carga lazy)
- [x] 2.2 Implementar `init()`: cargar `FaceDetector` desde `/mediapipe/face_detector_short_range.task` con delegado GPU (`Delegate.GPU`); si falla GPU, intentar `Delegate.CPU` como fallback
- [x] 2.3 Implementar `init()` continuación: cargar `FaceLandmarker` desde `/mediapipe/face_landmarker.task` (numFaces: 4, minFaceDetectionConfidence: 0.5, outputFaceBlendshapes: false, outputFacialTransformationMatrixes: false)
- [x] 2.4 Implementar `init()` continuación: cargar `PoseLandmarker` desde `/mediapipe/pose_landmarker_lite.task` (numPoses: 1, minPoseDetectionConfidence: 0.5)
- [x] 2.5 Implementar `detectFaces(frame)`: llamar a `FaceDetector.detectForVideo()` con timestamp, mapear `Detection[]` a `FaceDetectionSignal` con `face_count` y `FaceBox[]` normalizados (coordenadas 0..1)
- [x] 2.6 Implementar `detectFaceMesh(frame)`: llamar a `FaceLandmarker.detectForVideo()`, mapear landmarks a `FaceLandmark[]`, calcular gaze con `gazeFromIris()` (reutilizar helper existente de `MediaPipeVisionEngine.ts:118-130`), calcular embedding con `embeddingFromLandmarks()`
- [x] 2.7 Implementar `detectPose(frame)`: llamar a `PoseLandmarker.detectForVideo()`, mapear `NormalizedLandmark[]` a `PoseKeypoint[]`
- [x] 2.8 Implementar `processFrame(frame)`: internamente llamar a `detectFaces` y extraer `face_count` + `landmarks` del primer rostro para construir `FrameResult`
- [x] 2.9 Implementar `computeEmbedding(frames)`: delegar a `embeddingFromLandmarks(frames.flatMap(f => f.landmarks))` (igual que `MediaPipeVisionEngine`)
- [x] 2.10 Implementar `dispose()`: llamar a `.close()` en cada runner (FaceDetector, FaceLandmarker, PoseLandmarker) y resetear `ready = false`
- [x] 2.11 En `init()`: si WebGL no disponible o cualquier fetch de modelo falla con 404, throw un `Error` descriptivo que incluya el nombre del archivo faltante y el path esperado (`/mediapipe/<nombre>.task`)
- [x] 2.12 Escribir test unitario: `RealMediaPipeVisionEngine` es una instancia de `VisionEngine` (satisface el contrato de interfaz); mock de los runners de tasks-vision para verificar el mapeo de señales

## 3. Harness engine loader — lazy import

- [x] 3.1 Crear `frontend/src/vision/harnessEngineLoader.ts` que exporta `async function loadRealEngine(): Promise<VisionEngine>`
- [x] 3.2 Dentro de `loadRealEngine()`: usar `const { RealMediaPipeVisionEngine } = await import('./RealMediaPipeVisionEngine')` (dynamic import para garantizar chunk split en Vite)
- [x] 3.3 Instanciar y llamar `await engine.init()` dentro de `loadRealEngine()`; si `init()` tira, rechazar la promesa con el error original (sin swallow)
- [x] 3.4 Verificar en el build de Vite que `@mediapipe/tasks-vision` aparece en un chunk separado y NO en el chunk inicial (revisar `dist/` o `vite.config.ts` si se necesita `manualChunks`)

## 4. VisionOverlay — canvas superpuesto al video

- [x] 4.1 Crear `frontend/src/ui/VisionOverlay.tsx` como componente React que acepta props: `rawSignals: RawSignals | null`, `videoRef: RefObject<HTMLVideoElement>`, `showFullMesh?: boolean`, `showPose?: boolean`
- [x] 4.2 El componente renderiza un `<canvas>` con `position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none`; el canvas se sincroniza con las dimensiones del video via `ResizeObserver` o `useEffect` con `videoWidth`/`videoHeight`
- [x] 4.3 Implementar función `drawFrame(ctx, rawSignals, videoW, videoH)` que: (1) llama `clearRect(0, 0, videoW, videoH)`, (2) dibuja bounding boxes de `faceDetection.faces` escalando coordenadas normalizadas a píxeles, (3) dibuja label "Rostro N (XX%)" por cada box
- [x] 4.4 Implementar dibujo de landmarks del Face Mesh: si `faceMesh.landmarks.length > 0`, dibujar puntos de contorno de cara (eyes, eyebrows, nose bridge, mouth, oval — ~68 puntos del subconjunto canónico); si `showFullMesh === true`, dibujar los 468 puntos
- [x] 4.5 Implementar dibujo del vector gaze: desde el centro del primer bounding box (o centro del canvas si no hay box), dibujar una flecha/línea en dirección `faceMesh.gaze.x, faceMesh.gaze.y` escalada a pixels proporcional al alto del video
- [x] 4.6 Implementar dibujo de keypoints de pose (si `showPose && poseAvailable`): dibujar los puntos de shoulders, elbows, wrists, hips y sus conexiones de miembros como líneas
- [x] 4.7 Llamar a `drawFrame` en un `useEffect` que se dispara cuando `rawSignals` cambia
- [x] 4.8 Escribir test de VisionOverlay: dado `rawSignals` con 2 caras, verificar que `drawRect` fue llamado 2 veces (mock del canvas context 2D)

## 5. Integración en AdminDetectionHarness

- [x] 5.1 Agregar estado local `engineMode: 'simulated' | 'loading' | 'real-active' | 'load-error'` inicializado a `'simulated'`; agregar `engineError: string | null` para mensajes de error
- [x] 5.2 En el handler del botón "Iniciar": antes de crear el engine, setear `engineMode = 'loading'`; llamar a `loadRealEngine()` del loader; si resuelve, setear `engineMode = 'real-active'` y usar el engine real; si rechaza, setear `engineMode = 'load-error'` y `engineError = error.message`
- [x] 5.3 Eliminar los bloques `catch` que devuelven señales hardcodeadas para visión (líneas 469–487 actuales): reemplazar por propagación del error real al estado `load-error`
- [x] 5.4 Actualizar el banner de estado (capability `harness-legibility-layer`) para ser condicional: `'simulated'` → banner amarillo, `'loading'` → banner azul con spinner, `'real-active'` → banner verde, `'load-error'` → banner rojo con `engineError`
- [x] 5.5 Colocar `<VisionOverlay>` dentro del contenedor del `<video>` en el JSX del harness; pasarle `rawSignals` y `videoRef`; usar `position: relative` en el contenedor padre para que el absolute del canvas funcione
- [x] 5.6 Agregar toggle "Pose" y toggle "Mesh completo (468 pts)" en los controles del harness; pasar los estados a `<VisionOverlay>` como props `showPose` y `showFullMesh`
- [x] 5.7 El panel de señales crudas debe mostrar badge "REAL" (verde) o "SIM" (amarillo) según `engineMode`; la señal de `face_count` debe reflejar el valor real del motor cuando está activo
- [x] 5.8 Asegurar que el panel de propósito del harness (del C-29) sigue visible en todos los estados del motor — agregar si no está ya: "Esta es una herramienta diagnóstica admin. No genera evidencia de examen."

## 6. Actualización de CHANGES.md

- [x] 6.1 Agregar entrada `### [C-30] 'vision-real-harness'` en la sección "Refinamiento post-fundación" de `CHANGES.md`, con estado `[ ] propuesto`, scope, dependencias (`C-23`, `C-25`, `C-29`), governance ALTO, y referencia a los archivos del change
- [x] 6.2 Actualizar el contador de la sección "Resumen" en `CHANGES.md`: cambiar "29 changes" a "30 changes" y "C-21…C-29" a "C-21…C-30"

## 7. Validación final

- [x] 7.1 Correr `openspec validate --strict` sobre el change `c-30-vision-real-harness` y resolver cualquier error
- [x] 7.2 Verificar que el build de Vite no incluye `@mediapipe/tasks-vision` en el bundle inicial (revisar output de `vite build --reporter verbose` o similar)
- [x] 7.3 Verificar que los tests existentes del harness (C-23, C-25) siguen pasando sin cambios (el stub `MediaPipeVisionEngine` no fue modificado)
- [x] 7.4 Ejecutar el script de descarga de modelos en un entorno limpio y verificar que los tres archivos `.task` quedan en `frontend/public/mediapipe/`
