## 1. Fix Bug 1 — Limpieza de cámara al reiniciar el harness

- [x] 1.1 En `startHarness()` (`AdminDetectionHarness.tsx`), antes de llamar `getUserMedia`, agregar `videoRef.current.srcObject = null` y `videoRef.current.load()` para descartar cualquier frame o buffer anterior del decoder HTML5
- [x] 1.2 En el `useEffect` cleanup (líneas ~655–663), agregar `if (videoRef.current) { videoRef.current.srcObject = null; videoRef.current.load(); }` después de detener los tracks, para garantizar que al desmontar el `<video>` quede sin contenido
- [x] 1.3 Verificar que `stopHarness()` ya limpia `videoRef.current.srcObject = null` — si no, agregarlo; confirmar que `streamRef.current` también se setea a `null`
- [x] 1.4 Verificar que el `rawSignals` pasado a `<VisionOverlay>` se resetea a `{ faceDetection: null, ... }` tras `stopHarness()` — esto hace que `VisionOverlay` ejecute `clearRect` en su `useEffect` de dibujo (ya existe el condicional de limpieza)

## 2. Fix Bug 2 — Recalibración de umbrales de gaze en DEFAULT_CONFIG

- [x] 2.1 En `stateTransitionRules.ts`, actualizar `DEFAULT_CONFIG`: `gaze_deviation_threshold: 0.25` (antes 0.6), `gaze_sustained_ms: 2500` (antes 4000), `gaze_fixation_tolerance: 0.25` (antes 0.15)
- [x] 2.2 Agregar comentarios en `DEFAULT_CONFIG` documentando el rango práctico del vector iris (`~0.15–0.35` para desviación visible) y el razonamiento de cada valor calibrado

## 3. Fix Bug 2 — Promedio de ambos iris en RealMediaPipeVisionEngine

- [x] 3.1 En `RealMediaPipeVisionEngine.detectFaceMesh()` (~líneas 257–274), cuando ambos iris estén disponibles (landmarks 468 y 473), calcular `gazeLeft = gazeFromIris(iris468, corner33, corner133)` y `gazeRight = gazeFromIris(iris473, corner362, corner263)` y asignar `gaze = { x: (gazeLeft.x + gazeRight.x) / 2, y: (gazeLeft.y + gazeRight.y) / 2 }`
- [x] 3.2 Mantener el fallback de un solo iris cuando solo uno de los dos está disponible (comportamiento existente)
- [x] 3.3 Agregar comentario explicando por qué se promedian ambos iris (mayor cobertura, menor ruido)

## 4. Extensión de FrameSignals con head_yaw_deg

- [x] 4.1 En `stateTransitionRules.ts` (interfaz `FrameSignals`), agregar el campo `head_yaw_deg?: number` con comentario: `// Yaw de cabeza en grados (0 = frontal, + = derecha, - = izquierda). Opcional; si undefined, se ignora en evalGaze().`
- [x] 4.2 Agregar la constante de módulo `const HEAD_YAW_THRESHOLD_DEG = 20;` en `stateTransitionRules.ts` con comentario explicativo
- [x] 4.3 En `evalGaze()`, modificar la condición `deviated` para que sea `const deviated = (magnitude >= this.cfg.gaze_deviation_threshold) || (s.head_yaw_deg !== undefined && Math.abs(s.head_yaw_deg) > HEAD_YAW_THRESHOLD_DEG);`
- [x] 4.4 Verificar que la lógica del ancla (`drift`, `fixation_tolerance`) solo opera sobre el vector gaze `g` (no sobre `head_yaw_deg`) — el ancla sigue midiendo posición del iris para la "fijación sostenida"

## 5. Propagación de head_yaw_deg desde AdminDetectionHarness

- [x] 5.1 En `AdminDetectionHarness.tsx`, en el bucle de frames, después de obtener `poseSignal`, calcular `head_yaw_deg` aproximado: usando landmarks de hombros (índices 11 y 12 de `PoseSignal`) y su diferencia de coordenadas Y, estimar yaw; si `poseSignal` es null o los landmarks no están disponibles, `head_yaw_deg = undefined`
- [x] 5.2 En la llamada a `pipeline_.onSignals()`, agregar `head_yaw_deg` al objeto de señales

## 6. Actualización de CHANGES.md

- [x] 6.1 En `CHANGES.md`, agregar la entrada `C-35` en la sección "Refinamiento post-fundación" con estado `[ ]` propuesto, scope, dependencias (`C-23`, `C-25`, `C-30`, `C-32`, `C-33`), governance MEDIO, y la sección "Leer antes"
- [x] 6.2 Actualizar el conteo total de changes en la sección Resumen: de 34 → 35

## 7. Verificación manual

- [x] 7.1 **Bug 1 — verificación de cámara limpia**: iniciar el harness (cámara activa y corriendo), navegar a otra ruta (p.ej. `/admin`), volver a `/admin/detection-test`, verificar que el video no muestra frame congelado de la sesión anterior y que el harness arranca en estado `idle` (sin frames hasta presionar Iniciar) — QA manual OK
- [x] 7.2 **Bug 2 — verificación de mirada sostenida**: iniciar el harness con motor real activo, mirar sostenidamente hacia un lado por 3–4 segundos; verificar en el panel de eventos que `mirada_desviada_sostenida` aparece en el log; verificar que el medidor de riesgo (C-33) sube al menos 12 puntos (peso de evento "media" según `riskWeights.ts`) — QA manual OK
- [x] 7.3 **Verificación de no-regresión en Examen.tsx**: `grep` confirma cero referencias a `gaze_deviation_threshold` o `0.6` en `Examen.tsx`; el valor vive solo en `DEFAULT_CONFIG` (`stateTransitionRules.ts:113`)
