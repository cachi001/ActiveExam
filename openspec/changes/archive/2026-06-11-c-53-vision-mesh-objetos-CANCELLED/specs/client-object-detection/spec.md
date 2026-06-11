# Spec — client-object-detection

> Detección de objetos prohibidos en el cliente vía MediaPipe Object Detector detrás del motor abstraído (DD-17), produciendo el evento discreto `objeto_prohibido_detectado`. El cliente es un SENSOR NO CONFIABLE: emite señal, el backend re-infiere y firma server-side; el sistema NUNCA sanciona (L2.5).

## ADDED Requirements

### Requirement: Object Detector detrás del motor abstraído
El motor de visión SHALL exponer un método `detectObjects(frame)` en la interfaz `VisionEngine` que devuelve una `ObjectDetectionSignal` con la lista de objetos detectados (`label`, `confidence` 0..1, `box` normalizado). La implementación concreta (MediaPipe Object Detector) SHALL quedar detrás de la interfaz; el pipeline y las reglas NO SHALL referenciar tipos de MediaPipe, manteniendo la ruta a ONNX Runtime Web (DD-17).

#### Scenario: el motor real detecta objetos
- **WHEN** `RealMediaPipeVisionEngine.detectObjects(frame)` procesa un fotograma con un objeto visible
- **THEN** devuelve una `ObjectDetectionSignal` con uno o más `DetectedObject` con su `label` crudo del modelo, `confidence` y bounding box normalizado

#### Scenario: el stub no simula detecciones (fallback honesto)
- **WHEN** se usa el stub `MediaPipeVisionEngine.detectObjects(frame)`
- **THEN** devuelve `{ objects: [] }` sin inventar detecciones

#### Scenario: el pipeline no conoce MediaPipe
- **WHEN** se sustituye el motor por otra implementación de `VisionEngine`
- **THEN** el pipeline y las reglas siguen funcionando sin cambios porque dependen solo de `ObjectDetectionSignal`, no del detector concreto

### Requirement: Modelo de Object Detection self-hosted
El modelo de Object Detection SHALL servirse localmente desde `/mediapipe/` (soberanía de datos, RD-7), NUNCA desde un CDN externo en runtime, y SHALL cargarse fuera del bundle JS inicial (chunk split vía dynamic import) para no afectar el objetivo de bundle inicial < 500 KB.

#### Scenario: modelo cargado desde ruta local
- **WHEN** el motor real inicializa el Object Detector
- **THEN** carga el modelo desde una ruta bajo `/mediapipe/` con fallback de delegado GPU a CPU, y si el modelo falta lanza un error descriptivo con las instrucciones de descarga

#### Scenario: el modelo no entra en el bundle inicial
- **WHEN** se carga la aplicación
- **THEN** el detector de objetos y su modelo se cargan bajo demanda (dynamic import), no en el bundle inicial

### Requirement: Señal de objeto re-inferida server-side, sin sanción automática
La señal de Object Detection del cliente SHALL tratarse como SEÑAL, no como veredicto. El evento resultante SHALL viajar al backend con su screenshot para re-inferencia server-side; el cliente NUNCA SHALL aplicar una sanción ni emitir un veredicto de fraude (L2.5).

#### Scenario: el objeto detectado no sanciona
- **WHEN** el cliente detecta un objeto prohibido sostenido
- **THEN** emite un evento de proctoring para priorización y revisión humana, sin bloquear el examen ni decidir fraude

#### Scenario: el evento incluye captura para re-inferencia
- **WHEN** se emite el evento de objeto prohibido
- **THEN** se adjunta el screenshot del frame para que el backend re-infiera y firme server-side (el payload no transporta el frame crudo del detector)
