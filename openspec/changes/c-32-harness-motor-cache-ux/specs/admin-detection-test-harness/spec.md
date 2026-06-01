## MODIFIED Requirements

### Requirement: Harness usa motor real cuando disponible
When the real vision engine loads successfully, `AdminDetectionHarness` SHALL use real `FaceDetectionSignal`, `FaceMeshSignal`, and `PoseSignal` values (not hardcoded fallbacks) to drive the raw signals panel and the vision pipeline.

#### Scenario: catch de stub eliminado — señales reales o error
- **WHEN** the harness is running with the real engine active
- **THEN** the try/catch blocks that silently catch stub errors and return hardcoded signals (lines 469–487 of the original implementation) SHALL be replaced: errors from the real engine SHALL propagate to the harness error state instead of being swallowed

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

### Requirement: Banner de carga usa spinner amigable sin jerga técnica
When `engineMode === 'loading'`, the loading banner SHALL display a spinner and human-readable message without technical terms.

#### Scenario: banner de carga sin jerga técnica
- **WHEN** the harness is in `engineMode === 'loading'`
- **THEN** the loading banner SHALL show a visual spinner (animated icon) and the message "Preparando la cámara…" or equivalent non-technical wording
- **AND** the banner SHALL NOT contain "WASM", "MediaPipe", "MB", or references to file download size

### Requirement: Umbrales configurables con nombres en lenguaje claro
The threshold configuration panel SHALL display a human-readable primary label for each configurable field, with the raw technical key shown as secondary/reference text only.

#### Scenario: labels de umbrales en lenguaje claro
- **WHEN** the threshold configuration panel renders
- **THEN** each of the five threshold fields SHALL have a human-readable primary label (e.g., "Segundos sin rostro para alertar" for `face_absent_ms`)
- **AND** the raw technical key SHALL be visible as secondary de-emphasized text
- **AND** all inputs SHALL remain fully editable with the same validation behavior as before

### Requirement: Panel de detección de monitores con flujo de permiso
`AdminDetectionHarness` SHALL present a dedicated UI card for multi-monitor detection that guides the user through the `window-management` permission flow.

#### Scenario: navegador no soporta la API — mensaje claro
- **WHEN** the harness starts in a browser where `window.getScreenDetails` does not exist
- **THEN** the monitor detection card SHALL show an informational message about browser compatibility (requires Chrome or Edge over HTTPS) and no permission request button

#### Scenario: permiso no solicitado — botón "Detectar pantallas"
- **WHEN** the harness is running and `window.getScreenDetails` is available but permission has not been requested yet
- **THEN** a button "Detectar pantallas" SHALL be visible in the monitor card
- **AND** clicking it SHALL trigger `requestAndDetectExtraMonitor()` as a user gesture

#### Scenario: permiso concedido — señal activa integrada al pipeline
- **WHEN** the window-management permission is granted
- **THEN** the `extra_monitor` signal SHALL be visible in the monitor card and SHALL be fed into the vision pipeline as before
