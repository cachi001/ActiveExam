# vision-overlay-canvas

## Purpose

Define el componente `<VisionOverlay>` — un canvas superpuesto al video del harness que dibuja en tiempo real las señales del motor de visión: bounding boxes de rostros detectados con su confianza, landmarks del Face Mesh y vector de mirada, y keypoints de pose con sus conexiones. El canvas no captura eventos de puntero (no interfiere con la UI), se ajusta a las dimensiones del video y se limpia entre frames para reflejar fielmente cada inferencia.

## Requirements

### Requirement: Canvas overlay superpuesto al video
A `<VisionOverlay>` component SHALL render an HTML `<canvas>` element positioned absolutely over the `<video>` element in the harness. The canvas SHALL have `pointer-events: none` so it does not interfere with any click/touch on the video area.

#### Scenario: canvas cubre el video completo
- **WHEN** the harness is running and the video element is visible
- **THEN** the canvas SHALL match the video's display dimensions (width and height) via CSS `width: 100%; height: 100%` and the canvas internal resolution SHALL match the video's `videoWidth` × `videoHeight`

#### Scenario: canvas no bloquea interacciones
- **WHEN** the user interacts with controls beneath or around the video
- **THEN** pointer events SHALL pass through the canvas to underlying elements (`pointer-events: none`)

### Requirement: Dibujar bounding boxes de rostros detectados
For each face in `faceDetection.faces`, the overlay SHALL draw a bounding box rectangle using normalized `FaceBox` coordinates scaled to canvas pixel dimensions.

#### Scenario: cero rostros — canvas limpio
- **WHEN** `faceDetection.face_count === 0`
- **THEN** the canvas SHALL be cleared (no boxes drawn)

#### Scenario: un rostro detectado
- **WHEN** `faceDetection.face_count === 1`
- **THEN** one rectangle SHALL be drawn in the configured face box color, with a label "Rostro 1 (XX%)" showing the confidence score rounded to integer

#### Scenario: múltiples rostros — cada uno con su box y label
- **WHEN** `faceDetection.face_count > 1`
- **THEN** one rectangle and label SHALL be drawn per face, each numbered sequentially

### Requirement: Dibujar landmarks del Face Mesh
When `faceMesh.landmarks` is available and non-empty, the overlay SHALL draw landmark points over the detected face.

#### Scenario: 468 landmarks disponibles — dibujar subconjunto legible
- **WHEN** `faceMesh.landmarks.length === 468`
- **THEN** the overlay SHALL draw at least the key contour landmarks (eyes, eyebrows, nose, mouth, face oval) as small dots; full 468-point density SHALL be optional via a toggle

#### Scenario: vector gaze como línea/flecha
- **WHEN** `faceMesh.gaze` is available
- **THEN** a directional indicator (line or arrow) SHALL be drawn from the face center in the direction of the normalized gaze vector `{x, y}` scaled to canvas pixels

#### Scenario: landmarks no disponibles — no se dibuja mesh
- **WHEN** `faceMesh` is null or `faceMesh.landmarks` is empty
- **THEN** no landmark points or gaze indicator SHALL be drawn

### Requirement: Dibujar keypoints de pose (opcional)
When pose detection is active and keypoints are available, the overlay SHALL draw the body keypoints (shoulders, elbows, wrists, hips minimum) connected by limb lines.

#### Scenario: pose disponible — keypoints y conexiones
- **WHEN** `poseSignal.keypoints.length > 0` and pose overlay is enabled
- **THEN** each keypoint SHALL be drawn as a dot scaled by `visibility` (dimmer if low visibility), and limb connections SHALL be drawn as lines

#### Scenario: pose deshabilitada — no se dibuja
- **WHEN** pose overlay toggle is off or `poseAvailable === false`
- **THEN** no pose elements SHALL be drawn on the canvas

### Requirement: Canvas limpiado entre frames
The overlay SHALL clear the entire canvas at the beginning of each frame render cycle before drawing the new signals.

#### Scenario: limpieza entre frames
- **WHEN** a new frame's signals are received
- **THEN** `clearRect(0, 0, width, height)` SHALL be called before any drawing operation for that frame
