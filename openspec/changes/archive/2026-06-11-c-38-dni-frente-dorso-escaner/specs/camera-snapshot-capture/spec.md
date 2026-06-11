## ADDED Requirements

### Requirement: CameraSnapshotCapture soporta prop scannerCorners para marco estilo escáner
Cuando `shape='rect'` y `scannerCorners=true`, el componente SHALL renderizar 4 esquinas tipo escáner sobre el marco del video en vivo y en el preview. Cada esquina SHALL consistir en 2 segmentos perpendiculares (horizontal + vertical) realizados en CSS puro. La prop SHALL ser opcional (default `false`) y compatible hacia atrás: omitirla produce el comportamiento idéntico a C-37.

#### Scenario: Esquinas de escáner visibles con scannerCorners=true y shape='rect'
- **WHEN** `CameraSnapshotCapture` recibe `shape='rect'` y `scannerCorners={true}`
- **THEN** se renderizan 4 esquinas absolutas sobre el contenedor del video, una en cada vértice

#### Scenario: Sin esquinas cuando scannerCorners=false o ausente
- **WHEN** `CameraSnapshotCapture` recibe `scannerCorners={false}` o la prop no está presente
- **THEN** no se renderiza ningún elemento de esquina de escáner

#### Scenario: scannerCorners ignorado en shape='oval'
- **WHEN** `CameraSnapshotCapture` recibe `shape='oval'` y `scannerCorners={true}`
- **THEN** no se renderiza ningún elemento de esquina (prop silenciada por la condición `shape === 'rect'`)

#### Scenario: Esquinas visibles en el estado preview
- **WHEN** `scannerCorners=true` y el componente está en fase `preview`
- **THEN** las esquinas de escáner se mantienen visibles sobre la imagen de preview

### Requirement: CameraSnapshotCapture acepta prop facingMode para seleccionar cámara
El componente SHALL aceptar la prop opcional `facingMode?: ConstrainDOMString` (default: `'user'`). Cuando se especifica `'environment'`, `getUserMedia` SHALL solicitar la cámara trasera. Esto permite que el escaneo de DNI use cámara trasera en dispositivos móviles sin duplicar el componente.

#### Scenario: Cámara trasera solicitada con facingMode='environment'
- **WHEN** `CameraSnapshotCapture` recibe `facingMode="environment"`
- **THEN** `getUserMedia({ video: { facingMode: 'environment' } })` es invocado

#### Scenario: Cámara frontal por defecto sin prop facingMode
- **WHEN** `CameraSnapshotCapture` no recibe la prop `facingMode`
- **THEN** `getUserMedia({ video: { facingMode: 'user' } })` es invocado (comportamiento C-37 preservado)
