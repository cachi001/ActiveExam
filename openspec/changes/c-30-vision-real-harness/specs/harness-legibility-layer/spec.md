## MODIFIED Requirements

### Requirement: Banner de estado del motor es condicional
The engine status banner in `AdminDetectionHarness` SHALL reflect the actual state of the vision engine rather than showing a static "SIMULATED" message. It SHALL display one of four states: `simulated`, `loading`, `real-active`, or `load-error`.

#### Scenario: estado inicial — motor no solicitado (simulated)
- **WHEN** the harness has been loaded but "Iniciar" has not been pressed
- **THEN** the banner SHALL display with yellow/amber styling: "SEÑALES DE VISIÓN SIMULADAS — Motor MediaPipe en stub. Presioná Iniciar para activar el motor real."

#### Scenario: motor cargando (loading)
- **WHEN** "Iniciar" has been pressed and the real engine is being loaded and initialized
- **THEN** the banner SHALL display with blue styling and a loading indicator: "CARGANDO MOTOR MEDIAPIPE — Descargando modelos (~25-50 MB, solo la primera vez)..."

#### Scenario: motor real activo (real-active)
- **WHEN** `RealMediaPipeVisionEngine.init()` completes successfully
- **THEN** the banner SHALL display with green styling: "VISIÓN REAL (MediaPipe) — FaceDetector + FaceLandmarker + PoseLandmarker activos."

#### Scenario: error de carga (load-error)
- **WHEN** loading the real engine fails (WebGL absent, model file missing, timeout)
- **THEN** the banner SHALL display with red styling showing the specific error message, e.g. "ERROR: Modelo no encontrado — /mediapipe/face_detector_short_range.task. Ejecutá scripts/download-mediapipe-models.sh"

#### Scenario: no se simula tras error de carga
- **WHEN** the engine load fails
- **THEN** the harness SHALL NOT fall back to simulated signals — it SHALL remain stopped in `load-error` state until the user reloads or retries explicitly
