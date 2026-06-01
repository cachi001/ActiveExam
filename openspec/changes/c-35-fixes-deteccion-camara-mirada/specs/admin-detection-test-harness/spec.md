## MODIFIED Requirements

### Requirement: Harness usa motor real cuando disponible
When the real vision engine loads successfully, `AdminDetectionHarness` SHALL use real `FaceDetectionSignal`, `FaceMeshSignal`, and `PoseSignal` values (not hardcoded fallbacks) to drive the raw signals panel and the vision pipeline.

#### Scenario: catch de stub eliminado — señales reales o error
- **WHEN** the harness is running with the real engine active
- **THEN** the try/catch blocks that silently catch stub errors and return hardcoded signals SHALL be replaced: errors from the real engine SHALL propagate to the harness error state instead of being swallowed

#### Scenario: face_count refleja la cámara real
- **WHEN** the real engine is active and 2 faces are in front of the camera
- **THEN** `rawSignals.faceDetection.face_count` SHALL equal 2 and the signals panel SHALL display "2 rostros"

#### Scenario: overlay activo con motor real
- **WHEN** the real engine is active and a frame is processed
- **THEN** the `<VisionOverlay>` canvas SHALL receive the current `rawSignals` and redraw bounding boxes and landmarks for that frame

### Requirement: Panel de señales informa estado del motor
The raw signals panel in `AdminDetectionHarness` SHALL display a visual indicator distinguishing real signals from simulated ones.

#### Scenario: señal marcada como REAL
- **WHEN** the real engine is active and producing signals
- **THEN** each signal card SHALL display a "REAL" badge or indicator (e.g., green dot)

#### Scenario: señal marcada como SIMULADA
- **WHEN** the harness is in `simulated` state (real engine not loaded)
- **THEN** each signal card SHALL display a "SIM" badge matching the C-29 styling

### Requirement: El harness es solo herramienta de diagnóstico admin
`AdminDetectionHarness` SHALL clearly communicate that it is a diagnostic tool only and does not produce exam evidence, regardless of whether the real engine is active.

#### Scenario: advertencia de herramienta diagnóstica siempre visible
- **WHEN** the harness is in any state (simulated, loading, real-active, error)
- **THEN** the harness header panel SHALL display the diagnostic purpose statement from C-29, making clear this tool does not generate exam evidence and is for admin use only

### Requirement: Estado limpio al desmontar y al reiniciar el harness
Al navegar fuera del harness (desmontaje del componente) o al llamar `stopHarness()`, todos los recursos de cámara y renderizado SHALL liberarse completamente para que al volver a la página no haya frame congelado ni estado residual.

#### Scenario: cámara limpia al volver a la página
- **WHEN** el usuario navega fuera del harness y vuelve a `/admin/detection-test`
- **THEN** el elemento `<video>` SHALL no mostrar ningún frame de la sesión anterior — el video SHALL estar en estado vacío (sin srcObject) antes de que `startHarness()` asigne el nuevo stream

#### Scenario: srcObject nulo antes de asignar nuevo stream
- **WHEN** `startHarness()` se llama por segunda vez (re-mount o re-inicio)
- **THEN** SHALL llamar `videoRef.current.srcObject = null` y `videoRef.current.load()` ANTES de asignar el nuevo stream de `getUserMedia`, garantizando que el decoder HTML5 descarte cualquier buffer anterior

#### Scenario: tracks detenidos al desmontar sin pasar por stop
- **WHEN** el usuario navega fuera del harness mientras el harness está en estado `running` (sin presionar Detener)
- **THEN** el `useEffect` cleanup SHALL detener todos los tracks del stream activo y limpiar `streamRef.current`, cancelar el `frameLoopRef` interval, y llamar `disposeRealEngine()`

#### Scenario: canvas del overlay sin píxeles residuales
- **WHEN** el harness se detiene con `stopHarness()` o se desmonta
- **THEN** el canvas del `VisionOverlay` SHALL quedar sin contenido visible — el `clearRect` del canvas SHALL ejecutarse (vía rawSignals = null propagado al overlay o limpieza directa del canvas)
