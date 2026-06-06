## 1. Motor abstraído — Object Detection (DD-17)

> **(DIFERIDO — change futuro)** El dueño decidió diferir el Object Detection. Todo este grupo queda SIN implementar.

- [ ] 1.1 (DIFERIDO — change futuro) Añadir tipos `DetectedObject` (`label`, `confidence`, `box: FaceBox`) y `ObjectDetectionSignal` (`objects: DetectedObject[]`) a `frontend/src/vision/VisionEngine.ts`
- [ ] 1.2 (DIFERIDO — change futuro) Añadir `detectObjects(frame): Promise<ObjectDetectionSignal>` a la interfaz `VisionEngine`
- [ ] 1.3 (DIFERIDO — change futuro) Implementar `detectObjects` en el stub `frontend/src/vision/MediaPipeVisionEngine.ts` devolviendo `{ objects: [] }` (fallback honesto, sin simular)
- [ ] 1.4 (DIFERIDO — change futuro) En `frontend/src/vision/RealMediaPipeVisionEngine.ts`: importar `ObjectDetector` de `@mediapipe/tasks-vision`, añadir loader `loadObjectDetector` (delegado GPU→CPU + carga tolerante) y la propiedad/`dispose`
- [ ] 1.5 (DIFERIDO — change futuro) Implementar `detectObjects` en `RealMediaPipeVisionEngine` (mapear `result.detections` a `DetectedObject[]` con box normalizado a 0..1)
- [ ] 1.6 (DIFERIDO — change futuro) Cargar `object_detector.task` en `init()` (ruta `/mediapipe/object_detector.task`) y cerrarlo en `dispose()`

## 2. Modelo self-hosted

> **(DIFERIDO — change futuro)** Object Detection diferido.

- [ ] 2.1 (DIFERIDO — change futuro) Añadir la descarga de `object_detector.task` (EfficientDet-Lite0) a `scripts/download-mediapipe-models.sh` y `scripts/download-mediapipe-models.ps1`
- [ ] 2.2 (DIFERIDO — change futuro) Verificar que el modelo se sirve desde `/mediapipe/` y carga vía dynamic import (no entra al bundle inicial)

## 3. Reglas de transición — evento `objeto_prohibido_detectado`

> **(DIFERIDO — change futuro)** Object Detection diferido.

- [ ] 3.1 (DIFERIDO — change futuro) Extender `FrameSignals` en `frontend/src/proctoring/stateTransitionRules.ts` con `objects?: DetectedObject[]` (opcional, retrocompatible)
- [ ] 3.2 (DIFERIDO — change futuro) Añadir a `TransitionConfig` + `DEFAULT_CONFIG`: `object_confidence_threshold` (0.5), `object_detection_frames` (3) y `prohibited_object_labels` (`['cell phone','book','laptop']`)
- [ ] 3.3 (DIFERIDO — change futuro) Implementar `evalObjects(s, out)` con umbral sostenido + de-dup (análogo a `evalMultipleFaces`); emite `objeto_prohibido_detectado` severidad `alta`, `trigger_evidence: true`, payload `{ etiqueta, confianza, frames_consecutivos }`
- [ ] 3.4 (DIFERIDO — change futuro) Llamar `evalObjects` desde `process()`; no emitir cuando `objects` es `undefined`

## 4. Tipos y labels del evento

> **(DIFERIDO — change futuro)** Object Detection diferido.

- [ ] 4.1 (DIFERIDO — change futuro) Añadir `objeto_prohibido_detectado` a `TipoEvento` en `frontend/src/lib/types.ts`
- [ ] 4.2 (DIFERIDO — change futuro) Añadir entrada a `TIPO_EVENTO_LABEL` en `frontend/src/lib/api.ts` ('Objeto prohibido detectado')
- [ ] 4.3 (DIFERIDO — change futuro) Añadir caso en `descripcionEvento` para el nuevo tipo

## 5. Cableado en pipeline y consumidores

> **(DIFERIDO — change futuro)** Object Detection diferido.

- [ ] 5.1 (DIFERIDO — change futuro) En `frontend/src/proctoring/visionPipeline.ts` (`onFrame`): correr `engine.detectObjects(frame)` y pasar `objects` a las reglas
- [ ] 5.2 (DIFERIDO — change futuro) En `frontend/src/proctoring/useExamProctoring.ts` (`runFrameTick`): correr `detectObjects` en try/catch propio (degradación silenciosa) y pasar `objects` a `pipeline.onSignals`
- [ ] 5.3 (DIFERIDO — change futuro) En `frontend/src/screens/harness/frameProcessor.ts`: correr `detectObjects` y alimentar la señal para que el staff vea/registre los eventos de objeto

## 6. Overlay — limpiar verde, mesh 468 opt-in solo-staff

- [x] 6.1 En `frontend/src/ui/VisionOverlay.tsx`: que `showFullMesh === false` NO pinte el subconjunto canónico de 68 puntos; conservar box de rostro y gaze
- [x] 6.2 Que `showFullMesh === true` pinte los 468 puntos del mesh completo
- [x] 6.3 Ajustar copy del toggle en `frontend/src/screens/harness/CameraPanel.tsx` para dejar claro que el mesh completo es diagnóstico de staff
- [x] 6.4 Confirmar/garantizar que `useExamProctoring` no monta `VisionOverlay` (comentario-guardia en el flujo de examen)

## 7. Normalizar `face_count` a lenguaje humano

- [x] 7.1 Crear helper compartido (`frontend/src/lib/faceCountLabel.ts`): `formatRostros(n)` + `formatRostrosConOrigen(origen, n)` con fraseo cliente/servidor
- [x] 7.2 `frontend/src/screens/harness/EventLog.tsx:173`: reemplazar `srv:{n}` por "Servidor: {n} rostro(s)" vía helper
- [x] 7.3 `frontend/src/screens/proctoring/EventoCard.tsx:84,89`: reemplazar números pelados por fraseo humano rotulado, conservando el badge "Discrepancia"
- [x] 7.4 `frontend/src/screens/harness/VisionSignalsPanel.tsx`: usar el helper en la tarjeta de rostros (evitar duplicar pluralización)

## 8. Tests (sin mocks de DB; lógica pura y UI)

- [ ] 8.1 (DIFERIDO — change futuro) Test `evalObjects`: emite con objeto sostenido N frames; no emite con objeto instantáneo; no emite con etiqueta no prohibida; de-dup mientras persiste; `objects` undefined es retrocompatible
- [ ] 8.2 (DIFERIDO — change futuro) Test stub `MediaPipeVisionEngine.detectObjects` devuelve `{ objects: [] }`
- [x] 8.3 Test overlay (`VisionOverlay.test.ts`): con `showFullMesh=false` no dibuja puntos de mesh pero sí box/gaze; con `showFullMesh=true` dibuja los 468
- [x] 8.4 Test de regresión: el flujo de examen no instancia `VisionOverlay`
- [x] 8.5 Test del helper `face_count`: pluralización 0/1/N y fraseo cliente/servidor

## 9. Verificación final

- [x] 9.1 `openspec validate c-53-vision-mesh-objetos --strict` en verde
- [ ] 9.2 (PARCIAL — la parte de objeto DIFERIDA) Revisar que ningún cambio sanciona (L2.5); el overlay/face_count no alteran el flujo de evidencia. La parte "el evento de objeto viaja con screenshot para re-inferencia" queda diferida con el Object Detection.
