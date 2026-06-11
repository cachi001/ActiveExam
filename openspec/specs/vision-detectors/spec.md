# vision-detectors

## Purpose

Define los tres detectores de visión del cliente — Face Detection, Face Mesh y Pose — corriendo sobre WebAssembly + WebGL dentro de un Web Worker dedicado, con transferencia de buffers sin copias para no bloquear el hilo principal. Establece los fps objetivo de cada detector y lo que cada uno SHALL producir (bounding boxes con confianza, landmarks para mirada y embedding facial, keypoints de pose), de modo que las reglas de transición y la verificación silenciosa continua tengan las señales necesarias.

## Requirements

### Requirement: Tres detectores a sus fps objetivo
El motor SHALL ejecutar Face Detection (5–10 fps), Face Mesh (5–10 fps) y Pose (2–5 fps). Face Detection SHALL producir bounding boxes y score de confianza por rostro; Face Mesh SHALL producir landmarks para dirección de la mirada (iris) y el embedding facial para verificación silenciosa continua; Pose SHALL producir puntos clave del cuerpo para posturas de consulta.

#### Scenario: Face Mesh produce mirada y embedding
- **WHEN** Face Mesh procesa un fotograma con un rostro
- **THEN** produce los landmarks para estimar la dirección de la mirada y el embedding facial usable por la verificación silenciosa continua

#### Scenario: Face Detection produce conteo de rostros con confianza
- **WHEN** Face Detection procesa un fotograma
- **THEN** produce los bounding boxes y el score de confianza de cada rostro detectado

### Requirement: Ejecución en Web Worker con WASM+WebGL y buffers sin copias
Los detectores SHALL ejecutar sobre WebAssembly + WebGL dentro de un Web Worker dedicado, y la comunicación de los buffers de pixels SHALL usar transferencia sin copias para no bloquear el hilo principal.

#### Scenario: Inferencia fuera del hilo principal con transferencia de buffers
- **WHEN** el feed de la cámara se procesa
- **THEN** la inferencia ocurre en el Web Worker y los buffers de pixels se transfieren sin copias entre el hilo principal y el worker
