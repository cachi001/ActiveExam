## Why

El harness de diagnóstico `/admin/detection-test` presenta dos bugs que impiden validar el sistema de detección de manera confiable: (1) al navegar fuera y volver a la página, la cámara queda con un frame congelado de la sesión anterior, impidiendo reiniciar correctamente; (2) el evento `mirada_desviada_sostenida` casi nunca se emite porque el umbral de desviación (`gaze_deviation_threshold: 0.6`) es inalcanzable para el vector gaze basado únicamente en desplazamiento de iris, haciendo que el medidor de riesgo de C-33 no suba ante miradas laterales evidentes.

## What Changes

- **Fix Bug 1 — cámara trabada (frame congelado)**: garantizar que al desmontar el componente y al detener el harness se liberen tracks, se limpie `srcObject`, se resetee el poster/frame del `<video>`, se cancele el loop de frames, y se limpie el canvas del `VisionOverlay`; al volver a montar el harness el estado debe comenzar en `idle` limpio sin frame residual.
- **Fix Bug 2 — mirada sostenida floja**: recalibrar los umbrales de gaze en `DEFAULT_CONFIG` de `stateTransitionRules.ts` (`gaze_deviation_threshold` de 0.6 → 0.25, `gaze_fixation_tolerance` de 0.15 → 0.25) para que sean alcanzables con el vector iris; incorporar opcionalmente el yaw de cabeza desde `PoseSignal` como señal complementaria para mejorar la detección de mirada lateral sin cabeza frontal.
- **Verificación funcional manual**: dos tasks de verificación — salir/volver confirma cámara limpia; mirar sostenidamente a un lado sube el medidor de riesgo.

## Capabilities

### New Capabilities

_Ninguna: este change es corrección de bugs en capabilities existentes, sin nuevos contratos ni endpoints._

### Modified Capabilities

- `admin-detection-test-harness`: nuevo contrato de cleanup de cámara y canvas al desmontar/detener — garantía de estado idle limpio al re-montar.
- `state-transition-rules`: recalibración de `DEFAULT_CONFIG` (nuevos valores de `gaze_deviation_threshold` y `gaze_fixation_tolerance`); extensión de `FrameSignals` con campo `head_yaw_deg?: number` opcional para incorporar pose como señal complementaria en `evalGaze()`.
- `real-vision-engine-harness`: ajuste del flujo de extracción de gaze en `RealMediaPipeVisionEngine.detectFaceMesh()` — usar promedio de ambos iris (izquierdo y derecho) cuando ambos estén disponibles, para mayor rango de detección lateral.

## Impact

- **Archivos modificados**:
  - `frontend/src/screens/AdminDetectionHarness.tsx` — cleanup de stream/srcObject/canvas al desmontar y al stop; propagar `head_yaw_deg` extraído de `PoseSignal` al pipeline.
  - `frontend/src/proctoring/stateTransitionRules.ts` — `DEFAULT_CONFIG` recalibrado; `FrameSignals` con `head_yaw_deg?`; `evalGaze()` incorpora yaw como señal complementaria.
  - `frontend/src/vision/RealMediaPipeVisionEngine.ts` — `detectFaceMesh()` usa promedio de ambos iris cuando disponibles.
  - `frontend/src/ui/VisionOverlay.tsx` — limpiar canvas explícitamente cuando `rawSignals` sea null (ya limpia parcialmente; asegurar que el clearRect se ejecute también al desmontar).
- **Sin impacto en backend**: 100 % frontend/harness.
- **Sin impacto en flujo de examen**: `Examen.tsx` no usa `DEFAULT_CONFIG` directamente (usa config configurable desde `exam-config` backend). Los nuevos valores de `DEFAULT_CONFIG` sí afectan el harness y a cualquier instancia que no pise los defaults — verificar que el flujo `Examen.tsx` no dependa del valor hardcodeado 0.6.
- **Dependencias**: `C-23` (harness base), `C-25` (pipeline + FrameSignals), `C-30` (motor real + RealMediaPipeVisionEngine), `C-32` (cache motor + disposeRealEngine), `C-33` (medidor de riesgo que se beneficia del fix).
