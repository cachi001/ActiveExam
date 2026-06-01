## Context

El harness de diagnóstico admin (`/admin/detection-test`, `AdminDetectionHarness.tsx`) ejecuta el pipeline completo de visión del cliente (VisionEngine → VisionPipeline → StateTransitionRules → LocalHarnessEventSink) pero el motor de visión es un **stub** que tira error en todos sus métodos de detección (`detectFaces`, `detectFaceMesh`, `detectPose` — líneas 46–68 de `MediaPipeVisionEngine.ts`). El harness captura esos errores silenciosamente (líneas 469–487 de `AdminDetectionHarness.tsx`) y devuelve señales hardcodeadas (`face_count: 1`, gaze `{x: 0.03, y: 0.01}`).

El resultado es un harness diagnóstico que nunca diagnóstica nada real: el admin ve siempre 1 rostro independientemente de cuántas personas estén frente a la cámara, y no hay feedback visual de lo que MediaPipe detectaría.

C-29 ya agregó un banner "SEÑALES DE VISIÓN SIMULADAS" que documenta esta limitación honestamente. C-30 la resuelve: cablea `@mediapipe/tasks-vision` Tasks API **únicamente en el harness**, y dibuja un overlay visual sobre el video.

**Restricciones no negociables:**
- Soberanía de datos (RD-7): modelos locales, nunca CDN externo.
- Bundle < 500 KB (RD-8): lazy import, `@mediapipe/tasks-vision` nunca en el chunk inicial.
- Interfaz abstracta DD-17: el harness usa `VisionEngine`, no `@mediapipe/tasks-vision` directamente.
- Fallback honesto: error claro en UI si los modelos no cargan. Nunca silencioso.
- El flujo de examen NO se toca.

## Goals / Non-Goals

**Goals:**

- Implementar `RealMediaPipeVisionEngine` que satisface `VisionEngine` usando `@mediapipe/tasks-vision` Tasks API con FaceDetector + FaceLandmarker (468 landmarks + iris) + PoseLandmarker.
- Servir modelos `.task` y binarios WASM desde `frontend/public/mediapipe/` (local, self-hosted).
- Documentar cómo obtener los modelos (script de descarga o instrucción copiado manual).
- Cargar `@mediapipe/tasks-vision` con `import()` dinámico solo en la ruta del harness (chunk lazy).
- Dibujar overlay en `<canvas>` superpuesto al `<video>`: bounding boxes de rostros, puntos de Face Mesh, keypoints de pose.
- Actualizar el banner de C-29 para ser condicional: `SIMULADO` / `CARGANDO` / `VISIÓN REAL (MediaPipe)` / `ERROR DE CARGA`.
- Si el motor no puede inicializar (WebGL ausente, modelo no encontrado, timeout), mostrar error descriptivo en la UI. El harness queda en estado `error`, no en estado `simulado`.

**Non-Goals:**

- NO cablear el motor real en el flujo de examen (`Examen.tsx`, `VisionPipeline` en producción).
- NO emitir eventos al backend desde el motor real (el harness sigue siendo air-gapped).
- NO implementar re-inferencia server-side (eso es C-12, el harness es diagnóstico cliente puro).
- NO usar el motor real para biometría/liveness de enrollment (eso es C-09/C-22).
- NO subir los modelos `.task` al repositorio git si superan el límite razonable (~50 MB); en ese caso se documentan como artefactos de descarga externa (uno por uno desde `storage.googleapis.com/mediapipe-models` — storage oficial de MediaPipe, que el self-hosted descarga una vez al setup).
- NO usar WebGPU (evaluación diferida; prioridad WebGL/WASM conforme DD-17 y la recomendación A3 del knowledge base).

## Decisions

### D-1: Nueva clase `RealMediaPipeVisionEngine` en lugar de modificar el stub

**Decisión**: crear `frontend/src/vision/RealMediaPipeVisionEngine.ts` que implementa `VisionEngine`, sin tocar `MediaPipeVisionEngine.ts`.

**Alternativas consideradas**:
- A) Completar `MediaPipeVisionEngine.ts` directamente — descartado porque el stub actual tiene valor como documentación del contrato vacío y como punto de referencia para la ruta ONNX (DD-17). Tocarlo mezcla dos responsabilidades.
- B) Una sola clase con flag `mode: 'stub' | 'real'` — descartado: viola SRP y complica el lazy load (si la clase se importa en cualquier lugar, arrastra la dependencia tasks-vision).

**Rationale**: la separación permite que el harness importe dinámicamente solo `RealMediaPipeVisionEngine`, y el resto del código siga usando `MediaPipeVisionEngine` (stub) sin ningún cambio. La interfaz `VisionEngine` garantiza el contrato (DD-17).

### D-2: Lazy import en el harness con un loader módulo

**Decisión**: crear `frontend/src/vision/harnessEngineLoader.ts` que exporta una función `async loadRealEngine(): Promise<VisionEngine>`. Esta función usa `const { RealMediaPipeVisionEngine } = await import('./RealMediaPipeVisionEngine')` y devuelve una instancia ya inicializada. El harness llama a `loadRealEngine()` al presionar "Iniciar".

**Alternativas consideradas**:
- A) Importar directamente en `AdminDetectionHarness.tsx` con `import()` en el handler — funciona, pero mezcla la lógica de carga con el componente. Más difícil de testear y reutilizar.
- B) React.lazy / Suspense — aplica a componentes, no a clases de servicio. No aplica aquí.

**Rationale**: el loader actúa como anti-corruption layer entre el componente y la dependencia pesada. El chunk de Vite para `RealMediaPipeVisionEngine` se emite solo cuando se llama al loader.

### D-3: Modelos locales en `frontend/public/mediapipe/`

**Decisión**: los archivos `.task` se colocan en `frontend/public/mediapipe/` y la ruta base de los modelos se configura como `/mediapipe/`. Vite sirve `public/` como assets estáticos sin procesar. Los archivos `.task` y los `.wasm` se añaden a `.gitignore` (pueden ser decenas de MB). Se provee un script `scripts/download-mediapipe-models.sh` (y `.ps1` para Windows) que descarga los modelos desde `storage.googleapis.com/mediapipe-models` usando URLs fijadas por versión, y los coloca en `frontend/public/mediapipe/`.

**Modelos necesarios** (Tasks API v0.10.x — versión estable):
- `face_detector_short_range.task` (FaceDetector BlazeFace)
- `face_landmarker.task` (FaceLandmarker 468 landmarks + iris)
- `pose_landmarker_lite.task` (PoseLandmarker lite — balance performance/accuracy)

**Alternativas consideradas**:
- A) Bundlear los modelos dentro del bundle de Vite (import as base64) — descartado: 10-30 MB base64 en el bundle es inaceptable.
- B) Servir desde CDN en runtime (Google/jsdelivr) — descartado: viola la restricción de soberanía de datos y self-hosted (RD-7, CLAUDE.md). El proyecto debe funcionar sin acceso externo a internet.
- C) Servir desde el backend FastAPI — sobre-complicado para un harness diagnóstico; Nginx ya sirve `public/` de Vite.

### D-4: Overlay canvas superpuesto al video

**Decisión**: en `AdminDetectionHarness.tsx`, añadir un `<canvas ref={canvasRef}>` con CSS `position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;` sobre el `<video>`. En cada frame, el loop de frames dibuja sobre el canvas las señales detectadas. Se crea un componente React `<VisionOverlay>` que recibe `rawSignals` y `canvasRef` y centraliza el código de drawing.

**Qué se dibuja**:
- Por cada rostro en `faceDetection.faces`: rectángulo en rojo/naranja (color configurable) con label "Rostro N (score%)". Las coordenadas `FaceBox` (0..1) se escalan a píxeles del canvas.
- Si `faceMesh.landmarks` disponible: puntos de los 468 landmarks del Face Mesh en verde semi-transparente (radius 1-2px). Opcional: dibujar solo los 68 landmarks canónicos (subconjunto legible).
- Vector de gaze como una línea/flecha desde el centro del rostro en dirección normalizada.
- Si pose disponible: keypoints del cuerpo (shoulders, elbows, wrists, hips) conectados por líneas.

**Alternativas consideradas**:
- A) Usar la API de Drawing Utils de `@mediapipe/tasks-vision` — provee helpers para dibujar pero acoplaa el rendering a la librería. Descartado por DD-17 (no acoplar al proveedor concreto).
- B) Dibujar directamente en el canvas desde el harness sin componente — funciona pero mezcla lógica de rendering con lógica del harness. Un componente `<VisionOverlay>` aísla y permite testear el rendering independientemente.

### D-5: Banner condicional (actualización de C-29)

**Decisión**: el estado del motor en el harness se modela con 4 valores: `'simulated' | 'loading' | 'real-active' | 'load-error'`. Este estado alimenta el banner legado de C-29 (capability `harness-legibility-layer`):

- `simulated` (estado inicial, motor no solicitado): banner amarillo "SEÑALES DE VISIÓN SIMULADAS — Motor MediaPipe en stub. Presioná Iniciar para activar el motor real."
- `loading`: banner azul "CARGANDO MOTOR MEDIAPIPE — Descargando modelos (~25-50 MB, solo la primera vez)..."
- `real-active`: banner verde "VISIÓN REAL (MediaPipe) — FaceDetector + FaceLandmarker + PoseLandmarker activos."
- `load-error`: banner rojo con el mensaje de error concreto (ej. "Modelo no encontrado: /mediapipe/face_detector_short_range.task. Ejecutá scripts/download-mediapipe-models.sh"). El harness queda detenido; no silencia ni simula.

### D-6: Fallback honesto — no caer a simulación

**Decisión**: si `RealMediaPipeVisionEngine.init()` tira error (WebGL no disponible, fetch del modelo 404, timeout > 30s), el harness **no** vuelve al catch que devuelve señales simuladas. En cambio, propaga el error al estado `load-error` del banner y detiene el loop de frames. El usuario ve el problema real.

**Rationale**: el harness existe para diagnosticar problemas. Un harness que silencia errores de carga del motor es inútil como herramienta de diagnóstico. La honestidad es la restricción de diseño más importante (CLAUDE.md regla dura #5).

### D-7: `@mediapipe/tasks-vision` Tasks API vs `@mediapipe/face_mesh` legacy

**Decisión**: usar `@mediapipe/tasks-vision` (Tasks API, v0.10.x) que unifica FaceDetector + FaceLandmarker + PoseLandmarker en un solo paquete, con WASM y delegado WebGL unificados.

**Alternativas consideradas**:
- Legacy packages (`@mediapipe/face_mesh`, `@mediapipe/face_detection`, `@mediapipe/pose`) — descartados: Google los ha marcado como deprecated en favor de Tasks API. El knowledge base (11_ia_y_vision.md) menciona explícitamente que "Google ha reorganizado/deprecado partes de MediaPipe repetidamente" (DD-17). Tasks API es la superficie estable.

### D-8: Estructura de archivos del motor real

```
frontend/src/vision/
  VisionEngine.ts                    ← interfaz abstracta (sin cambios)
  MediaPipeVisionEngine.ts           ← stub existente (sin cambios)
  RealMediaPipeVisionEngine.ts       ← NUEVO: impl. real con @mediapipe/tasks-vision
  harnessEngineLoader.ts             ← NUEVO: lazy loader del motor real

frontend/src/ui/
  VisionOverlay.tsx                  ← NUEVO: componente canvas overlay

frontend/public/mediapipe/
  face_detector_short_range.task     ← descargado por script (no en git si >5MB)
  face_landmarker.task               ← descargado por script
  pose_landmarker_lite.task          ← descargado por script
  .gitkeep                           ← mantiene el directorio en git

scripts/
  download-mediapipe-models.sh       ← NUEVO: descarga modelos (Linux/macOS)
  download-mediapipe-models.ps1      ← NUEVO: descarga modelos (Windows PowerShell)
```

## Risks / Trade-offs

**[Riesgo 1: Tamaño de modelos y tiempo de carga inicial]**
Los tres modelos suman ~25-50 MB. La primera carga en un entorno nuevo puede tardar 10-30 segundos dependiendo del almacenamiento. El harness es solo para admins técnicos, no para alumnos en examen, por lo que la latencia de primera carga es aceptable. El banner de estado "CARGANDO" gestiona las expectativas.
Mitigación: usar solo `pose_landmarker_lite.task` (el más liviano); el overlay de pose es opcional pero deseable. Documentar en el banner el tamaño esperado de descarga de modelos.

**[Riesgo 2: WebGL no disponible]**
Tasks API de MediaPipe requiere WebGL para el delegado GPU. En algunos entornos corporativos o VMs sin GPU virtual, WebGL puede estar deshabilitado.
Mitigación: el fallback honesto (D-6) muestra un error descriptivo. Se puede añadir detección previa de WebGL y mostrar advertencia antes de intentar la carga. Fuera del scope de C-30 pero documentado como mejora.

**[Riesgo 3: Compatibilidad de versiones de `@mediapipe/tasks-vision`]**
La API de Tasks ha cambiado entre versiones (v0.10.x, v0.20.x). El script de descarga de modelos debe estar pinado a la misma versión del paquete npm.
Mitigación: fijar versión de `@mediapipe/tasks-vision` en `package.json` y versión de modelos en los scripts de descarga. Usar el mismo número de versión mayor.minor en ambos.

**[Riesgo 4: Rendimiento del overlay canvas en frames de bajo hardware]**
Dibujar 468 puntos de Face Mesh a 5 fps en hardware modesto puede afectar el rendimiento visual.
Mitigación: por defecto dibujar solo un subconjunto de landmarks (ej. 68 puntos canónicos o contorno de cara). La densidad completa de 468 puntos como opción configurable en los controles del harness.

**[Riesgo 5: CORS al cargar modelos en desarrollo local]**
Los archivos `.task` se cargan vía fetch desde las tareas internas de MediaPipe. En dev, Vite sirve `public/` correctamente sin CORS. En producción, Nginx sirve los estáticos. No debe haber problema.
Mitigación: documentar que los modelos deben estar en `public/mediapipe/` y no en una ubicación con CORS restrictivo.

**[Trade-off: El bundle crece en ~0 KB en el chunk inicial, pero el chunk lazy del harness puede ser grande]**
`@mediapipe/tasks-vision` más los archivos WASM pueden sumar varios MB en el chunk del harness. Esto es aceptable porque:
1. Solo los admins cargan esa ruta.
2. Los modelos y el WASM se pueden cachear en el navegador entre sesiones.
3. El bundle inicial del flujo de alumno NO cambia.

## Migration Plan

No hay migración de datos ni cambio en el backend. El deploy de C-30 requiere:

1. **Antes del deploy**: ejecutar `scripts/download-mediapipe-models.sh` (o `.ps1`) para poblar `frontend/public/mediapipe/`.
2. **Deploy estándar**: el build de Vite incluye los archivos de `public/mediapipe/` como assets estáticos. Nginx los sirve automáticamente.
3. **Rollback**: si hay problemas, basta con revertir el commit de C-30. El flujo de examen no fue tocado; el harness vuelve al comportamiento stub de C-23/C-29.

## Open Questions

- **OQ-1**: ¿Los archivos `.task` (~25-50 MB en total) entran en el repositorio git o solo se documentan como descarga? Recomendación: no subirlos al repo (`.gitignore`); usar el script de descarga en el setup del proyecto y en CI. Decidir con el equipo si se almacenan en el registry interno (MinIO del self-hosted) o se descargan directamente de `storage.googleapis.com/mediapipe-models`.
- **OQ-2**: ¿Se habilita el overlay de pose por defecto o solo bajo un toggle en los controles? Recomendación: toggle off por defecto (PoseLandmarker es el más pesado computacionalmente y los keypoints de cuerpo son más ruidosos que los de cara a 5 fps).
- **OQ-3**: ¿Qué versión específica de `@mediapipe/tasks-vision` se fija? Recomendación: `0.10.x` (la serie estable con WASM+WebGL consolidados). Verificar la versión más reciente del `0.10` al momento de implementar.
