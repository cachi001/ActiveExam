# 🚫 CANCELADO 2026-06-11 (parcial)

> **Hecho**: §6 (overlay verde por defecto removido, `showFullMesh` opt-in solo-staff), §7 (humanización `faceCountLabel`), §8 tests no-regresión — todo mergeado en `main` y en uso.
>
> **Cancelado**: §1–§5 + §9 (integración Object Detector MediaPipe). NO se va a implementar. El dueño decidió que objetos prohibidos (celular/libro/auriculares) NO son una señal de proctoring que sumemos en este horizonte — el costo de FP/FN + integración del detector adicional no justifica el esfuerzo dado el modelo L2.5 (decisión humana siempre). Si en el futuro se reabre, se propone un change nuevo.
>
> **Status efectivo**: 12/33 tasks ejecutadas; las 21 restantes se cancelan sin promover a backlog.

---

## Why (original)

Hoy el cliente de proctoring deja al descubierto tres asperezas que mezclan **diagnóstico de staff** con **experiencia del alumno** y exponen jerga cruda:

1. El **overlay verde** (mesh canónico de 68 puntos, `rgba(0,255,120,0.7)`) se dibuja por defecto en el harness sobre la cara, mientras el motor YA detecta los **468 landmarks completos** de Face Mesh pero solo los muestra detrás de un toggle. Pintar puntos sobre la cara del alumno es intrusivo y no aporta a su experiencia; el mesh completo es una herramienta de **diagnóstico de staff**, no algo que el examinado deba ver.
2. El sistema **no detecta objetos prohibidos** (celular, libro, auriculares). MediaPipe ofrece un Object Detector que corre en el mismo runtime WASM+WebGL ya cargado, pero no está integrado: hay una señal de proctoring valiosa que no estamos capturando.
3. El conteo de rostros (`face_count`) aparece **crudo** en la UI (`srv:2`, `Cliente 2 / Servidor 2`, números pelados), rompiendo la consistencia de lenguaje humano que el resto del panel ya respeta.

Es el momento porque el motor abstraído (C-11), las reglas de transición (C-11) y los fixes de detección/mirada (C-35) ya están en su lugar: agregar un detector más y limpiar la presentación es aditivo y de bajo riesgo, sin tocar el contrato de transporte ni el backend de re-inferencia.

## What Changes

- **Face Mesh completo (468) como modo diagnóstico solo-staff.** El mesh denso se renderiza únicamente en el harness/panel de staff y queda **opt-in** detrás del toggle existente. La cámara del **alumno durante el examen NUNCA dibuja puntos sobre su cara** — se garantiza que el flujo de examen (`useExamProctoring`) permanezca sin overlay.
- **Limpieza del overlay verde por defecto.** El mesh canónico de 68 puntos en verde neón deja de ser el render por defecto del overlay de diagnóstico; el box de rostro y el gaze se conservan como ayudas mínimas de staff. El examen del alumno no muestra ningún overlay de mesh.
- **NEW: Object Detection.** Integrar el MediaPipe Object Detector (modelo self-hosted en `frontend/public/mediapipe/`) detrás de la interfaz `VisionEngine` (motor abstraído, DD-17), produciendo una **señal continua de objetos detectados**. Una regla de transición sostenida convierte la presencia de un objeto prohibido (celular, libro, etc.) en un **nuevo evento discreto** `objeto_prohibido_detectado`.
- **NEW tipo de evento `objeto_prohibido_detectado`** en el contrato de eventos del cliente (señal, no veredicto): severidad alta + `trigger_evidence`, conforme al esquema de C-10. El backend re-infiere server-side; el cliente nunca decide fraude (L2.5).
- **Normalización de `face_count` a lenguaje humano** en toda la UI: badges y tarjetas dejan de mostrar `srv:N` / números pelados y pasan a un fraseo consistente ("2 rostros detectados", "Servidor: 2 rostros") con la lógica de pluralización ya usada en `VisionSignalsPanel`.

## Capabilities

### New Capabilities
- `client-object-detection`: detección de objetos prohibidos en el cliente vía MediaPipe Object Detector detrás del motor abstraído, regla de transición sostenida y nuevo evento discreto `objeto_prohibido_detectado` (señal cliente, re-inferida server-side, sin sanción automática).

### Modified Capabilities
- `vision-detectors`: el motor suma un cuarto detector (Object Detection) al conjunto de detectores de visión, ejecutándose en el mismo runtime WASM+WebGL.
- `vision-overlay-canvas`: el render del mesh deja de pintar el subconjunto verde por defecto; el mesh completo (468) pasa a ser opt-in solo-staff vía toggle, y el overlay se restringe al harness de diagnóstico (la cámara del alumno en examen no dibuja puntos sobre su cara).
- `state-transition-rules`: las reglas suman una transición sostenida que convierte la señal de objeto prohibido en el evento discreto `objeto_prohibido_detectado`.
- `harness-legibility-layer`: el conteo de rostros (`face_count`) se presenta en lenguaje humano consistente en todas las superficies de UI (panel de señales, card de evento, log), sin números crudos ni prefijos técnicos (`srv:`).

## Impact

- **Frontend — motor de visión** (`frontend/src/vision/`): `VisionEngine.ts` (interfaz + tipos `ObjectDetectionSignal`/`DetectedObject`), `RealMediaPipeVisionEngine.ts` (cargar `object_detector.task` con fallback GPU→CPU, implementar `detectObjects`), `MediaPipeVisionEngine.ts` (stub del nuevo método). Modelo nuevo en `frontend/public/mediapipe/object_detector.task` + scripts de descarga (`scripts/download-mediapipe-models.*`).
- **Frontend — pipeline y reglas** (`frontend/src/proctoring/`): `stateTransitionRules.ts` (campo `objects` en `FrameSignals`, `evalObjects` con umbral sostenido + config, lista de etiquetas prohibidas), `visionPipeline.ts` (pasar señal de objetos a las reglas), `useExamProctoring.ts` (`runFrameTick` corre `detectObjects` y alimenta la señal).
- **Frontend — overlay de diagnóstico** (`frontend/src/ui/VisionOverlay.tsx`, `frontend/src/screens/harness/CameraPanel.tsx`): el mesh canónico verde deja de ser default; `showFullMesh` controla el mesh 468 opt-in; el examen del alumno no monta `VisionOverlay`.
- **Frontend — presentación** (`frontend/src/screens/harness/{VisionSignalsPanel,EventLog}.tsx`, `frontend/src/screens/proctoring/EventoCard.tsx`): `face_count` humanizado; helper compartido de fraseo de rostros.
- **Tipos y labels** (`frontend/src/lib/types.ts`, `frontend/src/screens/harness/types.ts`, `frontend/src/lib/api.ts`): nuevo `TipoEvento` `objeto_prohibido_detectado` + entrada en `TIPO_EVENTO_LABEL` + `descripcionEvento`.
- **Sin cambios de contrato backend**: el evento viaja por el mismo endpoint slim (`POST /proctoring/sessions/{id}/events`). El backend re-infiere; este change no modifica el schema Pydantic del backend (el tipo es string libre en el slim). Se documenta el campo nuevo para el backend completo (C-12/C-24).
- **Dependencias**: `C-11` (vision-engine-detectores: motor abstraído + reglas de transición + pipeline), `C-35` (fixes-deteccion-camara-mirada: calibración de gaze/cabeza y overlay). Reusa el cableado del harness (C-23/C-30/C-32) y el flujo de examen lean (C-46). No bloquea ni es bloqueado por C-03 (no toca cola/transporte).
