## ADDED Requirements

### Requirement: Labels en lenguaje claro para los umbrales configurables del harness
The threshold configuration panel in `AdminDetectionHarness` SHALL display a human-readable name for each of the five configurable fields, with the raw technical key shown only as secondary/reference text.

#### Scenario: face_absent_ms muestra nombre comprensible
- **WHEN** the threshold panel renders the `face_absent_ms` field
- **THEN** the primary label SHALL read "Segundos sin rostro para alertar" (or equivalent clear description)
- **AND** the technical key `face_absent_ms` SHALL appear as secondary text (smaller, de-emphasized color) below or beside the primary label

#### Scenario: multiple_faces_frames muestra nombre comprensible
- **WHEN** the threshold panel renders the `multiple_faces_frames` field
- **THEN** the primary label SHALL read "Fotogramas con varios rostros para alertar" (or equivalent)
- **AND** the technical key SHALL appear as secondary text

#### Scenario: gaze_deviation_threshold muestra nombre comprensible
- **WHEN** the threshold panel renders the `gaze_deviation_threshold` field
- **THEN** the primary label SHALL read "Sensibilidad de mirada desviada" (or equivalent)
- **AND** the technical key SHALL appear as secondary text

#### Scenario: gaze_sustained_ms muestra nombre comprensible
- **WHEN** the threshold panel renders the `gaze_sustained_ms` field
- **THEN** the primary label SHALL read "Tiempo de mirada desviada para alertar" (or equivalent)
- **AND** the technical key SHALL appear as secondary text

#### Scenario: gaze_fixation_tolerance muestra nombre comprensible
- **WHEN** the threshold panel renders the `gaze_fixation_tolerance` field
- **THEN** the primary label SHALL read "Tolerancia de fijación de mirada" (or equivalent)
- **AND** the technical key SHALL appear as secondary text

#### Scenario: el campo de input sigue siendo editable
- **WHEN** the threshold labels are updated to use clear names
- **THEN** the numeric `<input>` for each field SHALL remain fully functional: the user can edit the value, validation errors are shown, and the config applies without restarting the engine
