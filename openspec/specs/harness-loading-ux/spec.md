# harness-loading-ux Specification

## Purpose
TBD - created by archiving change c-32-harness-motor-cache-ux. Update Purpose after archive.
## Requirements
### Requirement: Spinner amigable durante la carga del motor
When `AdminDetectionHarness` is in `engineMode === 'loading'`, the loading banner SHALL display a spinning progress indicator and human-readable text without technical jargon (no "WASM", no "MediaPipe", no file size in MB).

#### Scenario: banner de carga muestra spinner y texto amigable
- **WHEN** the harness is in `engineMode === 'loading'`
- **THEN** the banner SHALL display a visual spinner (animated icon) and the message "Preparando la cámara…" (or equivalent non-technical wording)
- **AND** the banner SHALL NOT contain the words "WASM", "MediaPipe", "MB", "modelos", "compila" or any reference to file download size

#### Scenario: mensaje diferenciado para primera carga vs carga con cache
- **WHEN** the engine is loading for the first time in a page session (no cached engine yet)
- **THEN** the banner SHOULD show a secondary note such as "Esto puede tardar unos segundos la primera vez."
- **WHEN** the engine has been loaded before in the session but disposed and is reloading
- **THEN** the same spinner is shown but the "primera vez" secondary note is NOT required

#### Scenario: accesibilidad del spinner
- **WHEN** the loading banner is rendered
- **THEN** the banner container SHALL have `role="status"` and `aria-live="polite"` so screen readers announce the loading state

