## Context

El harness de diagnóstico `/admin/detection-test` (`AdminDetectionHarness.tsx`) usa `getUserMedia` para la cámara y el motor `RealMediaPipeVisionEngine` (singleton de módulo, cacheado por C-32). En una SPA con routing por hash, navegar fuera del harness desmonta el componente y ejecuta el `useEffect` cleanup. El problema es que al volver, `getUserMedia` y el motor se reinician pero el `<video>` puede mostrar un frame residual y el `<canvas>` del `VisionOverlay` puede tener píxeles del render anterior.

El segundo bug está en `stateTransitionRules.ts`: `evalGaze()` requiere `magnitude >= 0.6` pero `gazeFromIris()` escala el desplazamiento del iris por el semi-ancho del ojo (`(irisCenter.x - cx) / halfWidth`). En la práctica el iris solo se mueve ~15–30 % del ancho del ojo en una desviación lateral fuerte, entregando magnitudes de 0.15–0.35 — muy por debajo del umbral de 0.6. Adicionalmente, `gaze_fixation_tolerance: 0.15` es menor que el movimiento natural de la cabeza, reiniciando el ancla constantemente e impidiendo que el contador de tiempo sostenido llegue a `gaze_sustained_ms`.

## Goals / Non-Goals

**Goals:**

- Al desmontar `AdminDetectionHarness` (navegar fuera) y al llamar `stopHarness()`, el `<video>` debe quedar sin frames ni srcObject y el canvas del overlay debe quedar limpio (clearRect).
- Al volver a montar el harness, el estado arranca en `idle` — ningún rastro visual de la sesión anterior.
- Recalibrar `DEFAULT_CONFIG` para que mirar 30–40 % hacia un lado (gaze real típico) dispare el evento `mirada_desviada_sostenida` en ~2–3 segundos.
- Incorporar el yaw de cabeza (`PoseSignal`) como señal complementaria en `evalGaze()` para mejorar la detección de miradas con giro de cabeza (sin reemplazar el iris, sino sumar).
- Mejorar `detectFaceMesh()` en `RealMediaPipeVisionEngine` usando el promedio de ambos iris (izquierdo y derecho) cuando ambos estén disponibles, ampliando el rango efectivo del vector.

**Non-Goals:**

- No modificar el flujo de examen real (`Examen.tsx`) más allá de verificar que no dependa del valor hardcodeado 0.6.
- No reemplazar el cálculo de iris por head pose — el iris sigue siendo la señal principal de gaze.
- No cambiar la severidad ni el tipo del evento `mirada_desviada_sostenida`.
- No tocar backend, WebSocket, ni ningún transport de producción.
- No implementar head pose estimación desde cero — usar los keypoints de `PoseSignal` ya disponibles (shoulders + nariz para estimar yaw aproximado).

## Decisions

### D-1: Limpieza de cámara — doble garantía (stop + cleanup)

**Decisión**: el fix garantiza la limpieza en DOS lugares:
1. `stopHarness()` — ya limpia tracks y srcObject. **Agregar** un `clearRect` explícito sobre el canvas del overlay y reset del `poster` del video.
2. `useEffect cleanup` — ya llama `disposeRealEngine()` y para tracks. **Agregar** `srcObject = null` explícito y una señal a `VisionOverlay` para que limpie su canvas.

**Mecanismo**: el `useEffect` cleanup ya pasa `rawSignals = null` (al setear `setRawSignals` con los valores vacíos en `stopHarness()`), lo cual hace que `VisionOverlay` ejecute `ctx.clearRect(...)` en su `useEffect` de dibujo. El problema es la race: si el desmontaje ocurre sin pasar por `stopHarness()` (p.ej. navegando directo con el harness corriendo), el cleanup del `useEffect` para los tracks pero no limpia el canvas. La solución es que el cleanup del `useEffect` también llame a `setRawSignals({ faceDetection: null, faceMesh: null, poseAvailable: false, poseSignal: null, frameTs: 0 })` — pero al desmontar no tiene sentido setear estado de React (el componente ya está desmontado). En cambio: **limpiar el canvas directamente desde el cleanup del useEffect** accediendo a `canvasRef` expuesto por `VisionOverlay` (opción B), o **limpiar el `<video>` directamente** desde el cleanup del `useEffect` en el harness (ya tenemos `videoRef`) seteando `videoRef.current.srcObject = null` y `videoRef.current.load()` para resetear el poster.

**Alternativa descartada**: pasar un `ref` de canvas de `VisionOverlay` hacia el padre. Innecesario — con `videoRef.current.srcObject = null` + `videoRef.current.load()` el video muestra el fondo vacío. El canvas del overlay ya se limpia cuando no recibe rawSignals (el `clearRect` ya existe en el `useEffect` de `VisionOverlay`), pero solo si el componente sigue montado. Al desmontar, el canvas desaparece del DOM, así que no importa.

**Conclusión**: el bug real es que al volver a montar el componente, el `<video>` puede tener el frame anterior visible hasta que el nuevo `getUserMedia` entregue el primer frame. El fix: en `startHarness()`, antes de asignar el nuevo `stream`, llamar `videoRef.current.srcObject = null` y `videoRef.current.load()` para forzar el estado "vacío" del elemento video. Esto borra el frame congelado instantáneamente.

### D-2: Recalibración de umbrales de gaze — valores concretos

**Análisis del rango real de `gazeFromIris()`**:
- El iris se desplaza ~15–30 % del semi-ancho del ojo en una desviación lateral visible.
- `gx = (irisCenter.x - cx) / halfWidth` → rango práctico ≈ ±0.15–0.35.
- Magnitud `hypot(gx, gy)` para mirada lateral pura ≈ 0.15–0.35.
- Umbral actual: 0.6 → prácticamente inalcanzable.

**Nuevos valores propuestos**:

| Campo | Valor actual | Valor propuesto | Razón |
|---|---|---|---|
| `gaze_deviation_threshold` | 0.6 | **0.25** | Alcanzable con desviación lateral ~30 % del semiancho; filtra micro-movimientos (0.10–0.15) |
| `gaze_sustained_ms` | 4000 | **2500** | Mantener la mirada 2.5 s lateral es suficiente señal; 4 s es demasiado largo para una prueba en el harness |
| `gaze_fixation_tolerance` | 0.15 | **0.25** | El movimiento natural de cabeza produce drifts de ~0.15–0.20; tolerancia 0.25 absorbe el ruido sin perder la señal |

**Impacto en `Examen.tsx`**: `Examen.tsx` no usa `DEFAULT_CONFIG` directamente — construye la config desde la API de backend (`exam-config`). Si el backend no devuelve umbrales, `TransitionConfig` usa defaults de `DEFAULT_CONFIG`. El cambio de 0.6 → 0.25 en `DEFAULT_CONFIG` SÍ afecta a exámenes sin config explicit, haciéndolos más sensibles. Esto es correcto: el umbral actual era un bug (casi nunca emitía). Los umbrales son configurables por institución (RN-EV-03); el admin puede ajustarlos en el harness y en la config del examen.

### D-3: Promedio de ambos iris en `detectFaceMesh()`

**Problema**: la implementación actual usa solo el iris izquierdo (landmark 468). Si el iris izquierdo no está disponible, hace fallback al derecho. No promedia ambos.

**Decisión**: cuando ambos iris estén disponibles (landmarks 468 y 473), calcular `gazeFromIris` para cada uno usando sus respectivas esquinas y promediar los dos vectores. Esto:
- Duplica la cobertura de señal (si un ojo está parcialmente ocluido, el otro compensa).
- Reduce ruido (promedio de dos mediciones independientes).
- No cambia el contrato de `FaceMeshSignal.gaze` — sigue siendo `{ x, y }`.

### D-4: Head yaw como señal complementaria en `evalGaze()`

**Problema**: algunos estudiantes miran hacia un lado girando la cabeza (sin mover los ojos) — el vector iris permanece near-zero mientras que la cabeza está visiblemente rotada.

**Decisión**: extender `FrameSignals` con `head_yaw_deg?: number` (opcional, 0 = frontal, ±90 = perfil). En `AdminDetectionHarness.tsx`, extraer el yaw aproximado de `PoseSignal` usando landmarks de hombros y nariz (ya disponibles desde C-30). En `evalGaze()`, combinar: `deviated = irisDeviated || Math.abs(head_yaw_deg) > HEAD_YAW_THRESHOLD_DEG`. Valor propuesto: `HEAD_YAW_THRESHOLD_DEG = 20` (giro de cabeza > 20° se considera desviación).

**Alternativa descartada**: usar los `facialTransformationMatrixes` de FaceLandmarker para obtener el yaw preciso. Más preciso pero requiere acceso a la API de transformación que no está actualmente expuesto por `VisionEngine`. El yaw aproximado desde PoseSignal es suficiente para el harness y no requiere cambiar la interfaz del motor.

**Campo en `FrameSignals`**: opcional (`head_yaw_deg?: number`) para retrocompatibilidad — `Examen.tsx` no pasa pose al pipeline (no tiene `PoseSignal` disponible); sin el campo el comportamiento es el mismo que antes.

### D-5: Constante `HEAD_YAW_THRESHOLD_DEG` — dónde vive

En `stateTransitionRules.ts` como constante de módulo (no parte de `TransitionConfig` en esta iteración — puede promoverse en un change posterior si se necesita configuración por institución). El valor de 20° es conservador y ajustable.

## Risks / Trade-offs

- **Umbral 0.25 más sensible → posibles falsos positivos en el flujo de examen**: miradas momentáneas de 0.25 pero sostenidas menos de 2500 ms no disparan — el `gaze_sustained_ms` actúa como filtro. Mitigar verificando manualmente en el harness antes de aplicar en producción.
- **`fixation_tolerance` 0.25 más permisivo → puede contar miradas no continuas como sostenidas**: si el estudiante mira ligeramente a ambos lados alternando, el ancla se resetea cuando el drift supera 0.25. Con 0.25 de tolerancia, movimientos de ±0.24 dentro de la misma zona no resetean. Esto es correcto — estamos midiendo si mira a "esa dirección general".
- **Yaw de PoseSignal basado en hombros**: el estimador es aproximado (asume que la diferencia de altura de hombros indica rotación). En algunos encuadres (persona de costado al principio) puede dar falso yaw. Mitigación: el campo es adicional al iris; si la pose no está disponible (`poseSignal === null`) se omite.
- **Race entre cleanup y re-mount**: en navegación SPA muy rápida (back/forward rápido), el `useEffect` cleanup podría ejecutarse DESPUÉS de que el nuevo mount ya inició `getUserMedia`. Mitigación: el flag `harnessState` actúa como guard — `startHarness()` retorna early si `harnessState !== 'idle'`; el cleanup resetea a `idle` solo si el componente ya está desmontado (no hay `setState` post-desmontaje).

## Migration Plan

1. Sin migración de datos — 100 % frontend.
2. Los nuevos valores de `DEFAULT_CONFIG` son retrocompatibles con instancias que pisan los defaults desde el backend.
3. El campo `head_yaw_deg?: number` es opcional en `FrameSignals` — no rompe ningún llamador existente.
4. Verificación manual antes de merge: (a) salir/volver → cámara limpia; (b) mirar sostenidamente a un lado 3 segundos → medidor de riesgo sube.

## Open Questions

- ¿Se debe promover `HEAD_YAW_THRESHOLD_DEG` a `TransitionConfig` (configurable por institución) en este mismo change o en uno posterior? → Decisión tomada: en este change queda como constante; se puede promover en C-36 si se necesita.
- ¿El flujo de examen `Examen.tsx` pasa `PoseSignal` al pipeline? → No actualmente. El campo `head_yaw_deg` es opcional — sin impacto en examen real.
