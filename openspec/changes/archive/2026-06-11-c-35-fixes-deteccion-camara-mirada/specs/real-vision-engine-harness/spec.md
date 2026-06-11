## MODIFIED Requirements

### Requirement: Motor real MediaPipe implementa VisionEngine
`RealMediaPipeVisionEngine` SHALL implement the `VisionEngine` interface (DD-17) using `@mediapipe/tasks-vision` Tasks API. It SHALL NOT couple any caller to the concrete MediaPipe library — all callers interact only through the `VisionEngine` contract.

#### Scenario: detectFaces retorna face_count real
- **WHEN** the camera feed has N faces in frame (N = 0, 1, 2+)
- **THEN** `detectFaces()` SHALL return a `FaceDetectionSignal` with `face_count === N` and one `FaceBox` per detected face with normalized coordinates (0..1) and a confidence score > 0

#### Scenario: detectFaceMesh retorna landmarks e iris reales con promedio de ambos iris
- **WHEN** at least one face is present in frame and both iris landmarks (468 and 473) are available
- **THEN** `detectFaceMesh()` SHALL return a `FaceMeshSignal` with `landmarks.length === 468`, a non-zero `gaze` vector computed as the **average of both iris vectors** (left iris 468 with corners 33/133, right iris 473 with corners 362/263), and a non-empty `embedding` array

#### Scenario: detectFaceMesh fallback a un solo iris
- **WHEN** only one iris landmark is available (e.g., left iris 468 present but right iris 473 absent)
- **THEN** `detectFaceMesh()` SHALL compute `gaze` from the available iris only (existing single-iris logic), returning a valid non-zero vector

#### Scenario: detectPose retorna keypoints reales
- **WHEN** a human body is visible in frame
- **THEN** `detectPose()` SHALL return a `PoseSignal` with `keypoints.length > 0` and normalized coordinates (0..1) per keypoint with visibility scores

#### Scenario: init falla cuando WebGL no está disponible
- **WHEN** `init()` is called in an environment without WebGL support
- **THEN** `init()` SHALL throw a descriptive Error identifying WebGL as the missing requirement (NOT silently succeed)

#### Scenario: dispose libera recursos
- **WHEN** `dispose()` is called after initialization
- **THEN** all MediaPipe runners (FaceDetector, FaceLandmarker, PoseLandmarker) SHALL be closed and GPU/WASM memory released

### Requirement: Carga de modelos desde rutas locales
`RealMediaPipeVisionEngine` SHALL load model files exclusively from local paths under `/mediapipe/` (served from `frontend/public/mediapipe/`). It SHALL NEVER hardcode or use external CDN URLs (e.g., `storage.googleapis.com`, `jsdelivr.net`) in runtime code.

#### Scenario: modelo cargado desde ruta local
- **WHEN** `init()` is called and model files exist at `/mediapipe/<model>.task`
- **THEN** all three runners SHALL initialize successfully using local file paths

#### Scenario: modelo no encontrado produce error descriptivo
- **WHEN** `init()` is called and a `.task` file is missing from `/mediapipe/`
- **THEN** `init()` SHALL throw an Error that names the missing file and instructs the user to run the download script

### Requirement: Motor real solo se instancia en el harness
The real engine (`RealMediaPipeVisionEngine`) SHALL only be instantiated within the admin detection harness route (`/admin/detection-test`). No other module, hook, or component in the production exam flow SHALL import or instantiate this class.

#### Scenario: flujo de examen no usa motor real
- **WHEN** the exam flow (`Examen.tsx`, `VisionPipeline` in production) is running
- **THEN** it SHALL use `MediaPipeVisionEngine` (the stub) or whichever engine is injected — `RealMediaPipeVisionEngine` SHALL NOT be in the dependency graph of any production exam component

#### Scenario: chunk lazy no entra al bundle principal
- **WHEN** the Vite production build is run
- **THEN** `@mediapipe/tasks-vision` and `RealMediaPipeVisionEngine` SHALL NOT appear in the initial JavaScript bundle (chunk split enforced by dynamic import)
