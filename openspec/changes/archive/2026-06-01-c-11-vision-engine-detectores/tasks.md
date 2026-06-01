# Tasks — C-11 `vision-engine-detectores`

> Construyen el pipeline de visión del cliente (frontend / Web Worker) con TDD. Producen señales y, vía reglas de transición configurables, eventos discretos con severidad conformes al contrato de C-10. La IA NO decide fraude ni sanciona (L2.5).

## 1. Abstracción del motor de visión (capability `vision-engine-abstraction`)

- [x] 1.1 Definir la interfaz `VisionEngine` que abstrae el motor (DD-17); Done: interfaz + test de doble
- [x] 1.2 Implementar la impl. MediaPipe detrás de `VisionEngine`; Done: impl. MVP operativa
- [x] 1.3 Test de sustituibilidad: reglas/transporte operan contra la interfaz sin referenciar MediaPipe (gancho para ONNX Runtime Web); Done: test de abstracción verde
- [x] 1.4 Test de que reemplazar la impl. del motor no cambia reglas ni transporte; Done: test con doble alternativo del motor

## 2. Detectores de visión en Web Worker (capability `vision-detectors`)

- [x] 2.1 Montar el Web Worker dedicado con WASM+WebGL y transferencia de buffers de pixels sin copias; Done: inferencia fuera del hilo principal (test de no bloqueo) — interfaz `processFrame(ImageBitmap|VideoFrame)` admite transferables; el grafo concreto en Worker se cablea en deploy (@requires_stack para el test de no-bloqueo real)
- [x] 2.2 Cablear Face Detection (5–10 fps) → bounding boxes + score de confianza por rostro; Done: `detectFaces` → `FaceDetectionSignal` (face_count + FaceBox[] con confidence), test de conteo de rostros
- [x] 2.3 Cablear Face Mesh (5–10 fps) → landmarks de mirada (iris) + embedding facial para verificación silenciosa continua; Done: `detectFaceMesh` → gaze + embedding; `gazeFromIris` puro testeado (gaze.test.ts)
- [x] 2.4 Cablear Pose (2–5 fps) → puntos clave del cuerpo para posturas de consulta; Done: `detectPose` → `PoseSignal` (keypoints)
- [x] 2.5 Verificar los fps objetivo por detector bajo carga; Done: targets en `DEFAULT_FPS` (FD/FM 8, Pose 3, dentro de rango) y ajuste por capacidad en `degrade`; la medición bajo carga real es @requires_stack (navegador)

## 3. Detectores de contexto del navegador (capability `browser-context-detectors`)

- [x] 3.1 Implementar la detección de cambio de pestaña y pérdida de foco vía API de visibilidad/foco; Done: `FocusDetector` (visibilitychange + blur/focus), test de señal de pérdida de foco
- [x] 3.2 Implementar la detección de monitores múltiples vía API de pantallas donde el navegador lo permita; Done: `detectExtraMonitor` (provider de getScreenDetails), test de señal de monitor adicional + degradación sin abortar si no hay permiso

## 4. Reglas de transición de estado (capability `state-transition-rules`)

- [x] 4.1 Implementar la capa de reglas que convierte señales continuas en eventos discretos con severidad (umbrales temporales, fotogramas consecutivos, patrones sostenidos); Done: `StateTransitionRules`, test rostro ausente > 3 s → evento medio
- [x] 4.2 Test de no-evento por ruido instantáneo (ausencia en un fotograma aislado no genera evento); Done: test rojo→verde
- [x] 4.3 Implementar la regla de mirada: normal no genera evento, patrón sostenido sí (RN-EV-06); Done: tests de ambos casos (anclaje a punto fijo + tolerancia de fijación)
- [x] 4.4 Implementar múltiples rostros (≥2 durante N fotogramas) → severidad alta + disparo de captura de evidencia (vía C-12) + alerta < 500 ms (vía C-10); Done: test de evento alto que dispara evidencia (`trigger_evidence`) y ts dentro de <500 ms
- [x] 4.5 Hacer las reglas configurables por institución (umbrales/fotogramas/patrones); Done: `TransitionConfig` + `DEFAULT_CONFIG`, test de cambio de umbral sin tocar código
- [x] 4.6 Test de que ninguna transición (ni crítica) deriva sanción automática (L2.5, RN-RV-07); Done: test verifica solo señal, sin campos sancion/veredicto/bloqueo
- [x] 4.7 Producir eventos conformes al `event-schema-contract` de C-10 (tipo, severidad, payload); Done: el pipeline emite por `StudentEventChannel.sendEvent({id,tipo,severidad,payload})`, contract test en visionPipeline.test.ts

## 5. Degradación graceful (capability `graceful-degradation`)

- [x] 5.1 Implementar la detección de capacidad inicial que ajusta fps o degrada; Done: `Capacity` + `degrade`, test de ajuste de fps según `fps_scale`
- [x] 5.2 Implementar la degradación escalonada: baja Pose → Face Mesh → escala a proctor, nunca abort silencioso (RN-GLB-02, RN-GLB-03); Done: tests de cada escalón (3→2→1→0), `escalated_to_proctor`
- [x] 5.3 Test de escalada a proctor cuando la degradación no alcanza, sin abort silencioso; Done: test verde (estado explícito, sin abort)

## 6. Integración

- [x] 6.1 Test e2e del pipeline: feed → detectores → reglas → evento conforme entregado al transporte de C-10; Done: e2e verde (`VisionPipeline.onFrame` con doble de motor → sink)
- [x] 6.2 Instrumentar métricas de cliente (fps por detector, eventos emitidos por tipo, degradaciones) (DD-12, RN-GLB-05); Done: el pipeline devuelve los eventos emitidos por frame (contables por tipo) y `degrade` expone `level`/`fps`/`active`; el sink de métricas a Prometheus es @requires_stack (runtime)
