## Why

El harness `/admin/detection-test` recrea y reinicializa el motor de visión en cada ciclo "Iniciar cámara", descargando y compilando los modelos WASM (~25–50 MB) repetidamente dentro de la misma sesión de página. Además, la interfaz usa jerga técnica (WASM, MediaPipe, MB, claves crudas como `face_absent_ms`) que resulta incomprensible para el personal no técnico que debe validar el sistema antes de un examen. Finalmente, la detección de monitores múltiples no solicita el permiso `window-management` al usuario, dejando la señal como "no determinable" incluso en navegadores que sí la soportan.

## What Changes

- **Cache del motor de visión**: `harnessEngineLoader.ts` cacheará la instancia de `RealMediaPipeVisionEngine` ya inicializada a nivel módulo. Si el motor ya está en estado `ready`, `loadRealEngine()` devuelve la instancia cacheada sin llamar `init()` de nuevo. La descarga/compilación WASM ocurre UNA sola vez por sesión de página. Se expone `disposeRealEngine()` para liberar el cache explícitamente cuando el componente se desmonta o ante un error irrecuperable.
- **Spinner amigable**: El estado `'loading'` del banner condicional de C-29/C-30 reemplaza el texto técnico ("CARGANDO MOTOR MEDIAPIPE… Descargando modelos y compilando WASM (~25–50 MB, solo la primera vez)") por un spinner animado + mensaje en lenguaje claro ("Preparando la cámara…"), sin mención de MB, WASM ni MediaPipe.
- **Config de umbrales en lenguaje claro**: Los labels crudos (`face_absent_ms`, `multiple_faces_frames`, `gaze_deviation_threshold`, `gaze_sustained_ms`, `gaze_fixation_tolerance`) del panel de configuración se reemplazan por nombres en español claro, con la clave técnica como texto secundario/tooltip. Se reutiliza el componente `<Term>` (C-28) para la clave técnica cuando corresponda.
- **Flujo de permiso Window Management**: `detectExtraMonitor` y el harness incorporan un flujo explícito para solicitar el permiso `window-management` mediante un gesto del usuario (botón "Detectar pantallas"). Si el navegador no soporta la API → mensaje explicativo (requiere Chrome/Edge sobre HTTPS). Si la API está disponible pero falta permiso → botón para solicitarlo. NO requiere backend.

## Capabilities

### New Capabilities

- `harness-engine-cache`: Mecanismo de cache a nivel módulo en `harnessEngineLoader.ts` que evita la re-descarga/re-compilación del motor WASM en cada ciclo "Iniciar cámara" dentro de la misma sesión de página. Expone `loadRealEngine()` (con cache) y `disposeRealEngine()` (para limpieza explícita).
- `harness-loading-ux`: Spinner y mensajería amigable para el estado de carga del motor, sin jerga técnica (WASM, MediaPipe, MB). Dirigido a personal no técnico.
- `harness-threshold-labels`: Nombres en lenguaje claro para los cinco umbrales configurables del harness, con clave técnica como referencia secundaria (tooltip o texto pequeño).
- `window-management-permission-flow`: Flujo UX para solicitar el permiso `window-management` al usuario desde el harness, con detección de soporte del navegador y mensajería clara ante falta de permiso o API no disponible.

### Modified Capabilities

- `harness-model-loader` (C-30): `loadRealEngine()` ahora implementa cache singleton a nivel módulo; nuevo export `disposeRealEngine()`. Comportamiento de error y fallback honesto sin cambios.
- `admin-detection-test-harness` (C-23): banner de carga actualizado (spinner + texto claro), labels de umbrales en lenguaje claro, flujo de permiso de monitor integrado en el panel de señales de entorno.
- `browser-context-detectors` (C-25): `detectExtraMonitor` expone variante que acepta un `requestPermission` flag para disparar `getScreenDetails()` como gesto del usuario; el detector pasivo permanece sin cambios.

## Impact

- `frontend/src/vision/harnessEngineLoader.ts` — cache singleton del motor, nuevo `disposeRealEngine()`
- `frontend/src/screens/AdminDetectionHarness.tsx` — spinner/mensaje de carga, labels claros de umbrales, flujo de permiso de monitor
- `frontend/src/proctoring/contextDetectors.ts` — `detectExtraMonitor` con soporte de solicitud de permiso explícita
- No hay cambios de backend, contratos de API, ni lógica de detección o scoring
- El banner condicional de C-29/C-30 (estados simulated/loading/real-active/load-error) se mantiene; solo el texto del estado `loading` cambia
