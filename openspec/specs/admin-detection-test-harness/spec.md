## MODIFIED Requirements

### Requirement: Harness usa motor real cuando disponible
When the real vision engine loads successfully, `AdminDetectionHarness` SHALL use real `FaceDetectionSignal`, `FaceMeshSignal`, and `PoseSignal` values (not hardcoded fallbacks) to drive the raw signals panel and the vision pipeline.

#### Scenario: catch de stub eliminado — señales reales o error
- **WHEN** the harness is running with the real engine active
- **THEN** the try/catch blocks that silently catch stub errors and return hardcoded signals (lines 469–487 of the current implementation) SHALL be replaced: errors from the real engine SHALL propagate to the harness error state instead of being swallowed

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
