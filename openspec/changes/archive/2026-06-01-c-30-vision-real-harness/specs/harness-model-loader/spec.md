## ADDED Requirements

### Requirement: Loader async para el motor real
`harnessEngineLoader.ts` SHALL export an async function `loadRealEngine(): Promise<VisionEngine>` that dynamically imports `RealMediaPipeVisionEngine`, instantiates it, calls `init()`, and returns the ready instance.

#### Scenario: carga exitosa devuelve motor inicializado
- **WHEN** `loadRealEngine()` is called and all model files are present
- **THEN** it SHALL return a `VisionEngine` instance that is ready to process frames (i.e., `init()` already called successfully)

#### Scenario: error de carga propaga el error original
- **WHEN** `loadRealEngine()` is called and `init()` throws (model missing, WebGL absent)
- **THEN** `loadRealEngine()` SHALL reject with the original error (NOT swallow it or return a simulated engine)

### Requirement: Script de descarga de modelos MediaPipe
The project SHALL provide scripts `scripts/download-mediapipe-models.sh` (bash) and `scripts/download-mediapipe-models.ps1` (PowerShell) that download the three required `.task` model files from pinned versioned URLs at `storage.googleapis.com/mediapipe-models` and place them in `frontend/public/mediapipe/`.

#### Scenario: script descarga los tres modelos con versión fijada
- **WHEN** the script is executed in the project root
- **THEN** `frontend/public/mediapipe/face_detector_short_range.task`, `frontend/public/mediapipe/face_landmarker.task`, and `frontend/public/mediapipe/pose_landmarker_lite.task` SHALL be present after completion, at the exact version pinned in the script

#### Scenario: script verifica integridad opcional
- **WHEN** the script completes the download
- **THEN** it SHOULD print the size of each downloaded file so the operator can verify the download was not truncated

#### Scenario: modelos fuera del repositorio git
- **WHEN** the `.gitignore` is evaluated
- **THEN** `frontend/public/mediapipe/*.task` and `frontend/public/mediapipe/*.wasm` SHALL be listed in `.gitignore`, and a `frontend/public/mediapipe/.gitkeep` SHALL keep the directory tracked

### Requirement: Documentar el proceso de setup de modelos
The README or setup documentation SHALL clearly describe that running the download script is required before the harness can use the real vision engine.

#### Scenario: README indica el paso de descarga de modelos
- **WHEN** a developer sets up the project for the first time
- **THEN** the setup instructions SHALL include an explicit step: "Run `scripts/download-mediapipe-models.sh` (or `.ps1`) to download vision models required for the admin detection harness"
