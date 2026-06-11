## Context

El pipeline de visión del cliente (C-11) corre sobre un **motor abstraído** (`VisionEngine`, DD-17) con tres detectores ya operativos: Face Detection, Face Mesh (468 landmarks reales) y Pose. El motor real `RealMediaPipeVisionEngine` (`frontend/src/vision/RealMediaPipeVisionEngine.ts`) carga modelos self-hosted desde `/mediapipe/` y los expone vía `detectFaces`/`detectFaceMesh`/`detectPose`. El pipeline (`visionPipeline.ts`) → reglas (`stateTransitionRules.ts`) → sink convierten señales continuas en eventos discretos conformes a C-10.

Hay **dos consumidores** del motor, con responsabilidades distintas:
- **Harness de diagnóstico** (`AdminDetectionHarness` + `frontend/src/screens/harness/*` + `VisionOverlay.tsx`): herramienta de **staff**. Dibuja un canvas overlay sobre el video con boxes, mesh y gaze. Hoy el mesh por defecto es el subconjunto canónico de 68 puntos en verde neón (`COLOR_MESH_CANONICAL = rgba(0,255,120,0.7)`, `VisionOverlay.tsx:66`), y el mesh completo de 468 es opt-in vía el toggle `showFullMesh` (`CameraPanel.tsx:80-91`).
- **Examen del alumno** (`useExamProctoring.ts` + `runFrameTick`): versión **LEAN sin overlay**. Corre `detectFaces`/`detectFaceMesh`, evalúa reglas con `onSignals` y streamea eventos+screenshot al backend slim. **No monta `VisionOverlay` ni dibuja sobre la cara** — verificado en `useExamProctoring.ts:419-470` (no hay referencia a canvas/overlay).

Estado verificado relevante:
- Object Detection **no existe** (0 referencias a `ObjectDetector` en `src/`). Hay que añadir el modelo + integrarlo al motor + nuevo evento.
- `face_count` crudo: `EventLog.tsx:173` (`srv:{faceCountServer}`), `EventoCard.tsx:84,89` (Cliente/Servidor números pelados). `VisionSignalsPanel.tsx:69-74` ya humaniza la tarjeta principal de rostros pero el accordion técnico es crudo (aceptable, está rotulado "detalle técnico").
- Tipos de evento en `lib/types.ts:16-25` y `TIPO_EVENTO_LABEL` en `lib/api.ts:998-1008`; falta `objeto_prohibido_detectado`.

Constraints duros del proyecto: motor abstraído (DD-17), cliente = sensor no confiable (re-inferencia server-side), L2.5 (nunca sanciona), Pydantic `extra='forbid'`, snake_case Python, PascalCase componentes React. KB de referencia: `knowledge-base/11_ia_y_vision.md` (detectores, eventos discretos, limitaciones, re-inferencia) y `knowledge-base/12_biometria_y_liveness.md`.

## Goals / Non-Goals

**Goals:**
- Integrar MediaPipe Object Detector detrás de `VisionEngine` (`detectObjects`), self-hosted, sin romper la abstracción ni el bundle inicial (chunk split vía dynamic import, igual que el resto de modelos).
- Producir un nuevo evento discreto `objeto_prohibido_detectado` mediante una regla de transición **sostenida** (no por un frame aislado), conforme al contrato de C-10. Severidad alta + `trigger_evidence`.
- Mover el mesh completo (468) a **opt-in solo-staff** en el harness y **eliminar el mesh verde por defecto**; conservar boxes y gaze como ayudas mínimas de staff.
- Garantizar que el flujo de examen del alumno **nunca dibuja puntos sobre su cara** (sin overlay).
- Normalizar `face_count` a lenguaje humano consistente en panel de señales, card de evento y log, con un helper compartido de fraseo/pluralización.

**Non-Goals:**
- NO implementar la re-inferencia server-side del objeto (eso es C-12/C-24 / backend completo). El cliente solo emite la señal; el backend slim recibe el evento como tipo string libre.
- NO añadir validación de schema Pydantic nueva en el backend (el slim acepta `tipo` libre). Se documenta el campo para el backend completo.
- NO cambiar el transporte ni la cola (no toca C-03 / C-10).
- NO sancionar ni puntuar de forma distinta a los demás eventos (L2.5: prioriza, no decide).
- NO reescribir el harness ni el flujo de examen: cambios aditivos sobre el cableado existente.

## Decisions

### D1 — Object Detector detrás de `VisionEngine`, no acoplado a MediaPipe
Añadir a la interfaz `VisionEngine` (`frontend/src/vision/VisionEngine.ts`) un método `detectObjects(frame): Promise<ObjectDetectionSignal>` y los tipos `DetectedObject` / `ObjectDetectionSignal`. El pipeline y las reglas conocen SOLO la señal, nunca el tipo de MediaPipe (igual que con Face/Pose).

```ts
export interface DetectedObject {
  label: string;        // categoría cruda del modelo (ej. 'cell phone', 'book')
  confidence: number;   // 0..1
  box: FaceBox;         // bounding box normalizada (reutiliza la forma de FaceBox)
}
export interface ObjectDetectionSignal {
  objects: DetectedObject[];
}
```

- `RealMediaPipeVisionEngine` carga `object_detector.task` (modelo EfficientDet-Lite0 de MediaPipe Tasks) con el mismo patrón GPU→CPU fallback y `checkModelNotFound` que los otros loaders, e implementa `detectObjects`.
- `MediaPipeVisionEngine` (stub) implementa `detectObjects` devolviendo `{ objects: [] }` (fallback honesto, no simula detecciones).
- **Alternativa descartada**: pasar el `ObjectDetector` crudo al pipeline → rompe DD-17 y obliga a reescribir el pipeline al migrar a ONNX.

### D2 — Lista de etiquetas prohibidas como configuración, no hardcode disperso
El modelo COCO/EfficientDet devuelve labels genéricos (`cell phone`, `book`, `laptop`, `remote`, `keyboard`…). La **decisión de cuáles son "prohibidos"** vive en las reglas de transición como una lista configurable (`prohibited_object_labels`), con default conservador (`['cell phone', 'book', 'laptop']`). Esto mantiene la política de negocio en la capa de reglas (configurable por institución, como `TransitionConfig`), no en el motor (que es un sensor agnóstico).
- **Alternativa descartada**: filtrar en el motor → mezcla política de negocio con el sensor; rompe la separación señal/regla del KB §"De inferencia continua a eventos discretos".

### D3 — Regla sostenida `evalObjects`, no por frame aislado
Análogo a `evalMultipleFaces`: un objeto prohibido debe persistir **N frames consecutivos** (`object_detection_frames`, default 3) por encima de un umbral de confianza (`object_confidence_threshold`, default 0.5) antes de emitir. Filtra el ruido (un objeto que cruza el cuadro un instante). De-dup: no re-emite mientras el objeto persiste; se resetea cuando desaparece. Evento:

```
tipo: 'objeto_prohibido_detectado'
severidad: 'alta'
payload: { etiqueta, confianza, frames_consecutivos }
trigger_evidence: true   // severidad alta → captura de evidencia (C-12) + alerta <500ms
```

`FrameSignals` suma `objects?: DetectedObject[]` (opcional, retrocompatible: las reglas lo ignoran si `undefined`). El campo `confianza` se redondea; el payload nunca lleva el frame crudo (sensor no confiable: la imagen va por el screenshot del evento, re-hasheada server-side).

### D4 — Mesh: eliminar verde por defecto, 468 opt-in solo-staff, examen sin overlay
En `VisionOverlay.tsx`:
- El render **por defecto** (`showFullMesh === false`) deja de pintar el subconjunto canónico de 68 puntos verdes. Se conserva el **box de rostro** y el **gaze** (ayudas mínimas de diagnóstico de staff que no son "puntos sobre la cara"). Esto satisface "limpiar el overlay verde".
- El **mesh completo (468)** se pinta SOLO cuando `showFullMesh === true` (toggle del staff en `CameraPanel.tsx`). Se ajusta el copy del toggle para dejar claro que es diagnóstico.
- El **examen del alumno** (`useExamProctoring`) ya no monta overlay → no requiere cambio funcional, pero se documenta/asegura con la spec y, si hace falta, un comentario-guardia para que nadie cablee `VisionOverlay` en el examen.
- **Alternativa descartada**: borrar `CANONICAL_68_INDICES` por completo → se pierde la opción de un mesh "ligero" si el staff lo quisiera en el futuro; mejor dejar el código pero no usarlo como default (o reservarlo bajo el mismo toggle). Decisión: el default no dibuja mesh; `showFullMesh` dibuja los 468.

### D5 — `face_count` humanizado vía helper compartido
Extraer un helper de presentación (ej. `frontend/src/lib/faceCountLabel.ts` o reusar el patrón ya en `VisionSignalsPanel`) que devuelva texto humano: `formatRostros(n) → 'sin rostros' | '1 rostro detectado' | 'N rostros detectados'`, y para origen cliente/servidor un fraseo con etiqueta ("Cliente: 2 rostros" / "Servidor: 2 rostros"). Aplicarlo en:
- `EventLog.tsx:173` — reemplazar `srv:{n}` por `Servidor: {n} rostro(s)`.
- `EventoCard.tsx:84,89` — reemplazar números pelados por el fraseo humano, conservando el badge "Discrepancia".
- `VisionSignalsPanel.tsx` — la tarjeta principal ya está humanizada; usar el helper para consistencia y no duplicar la lógica de pluralización.
- **Alternativa descartada**: humanizar inline en cada archivo → duplica la pluralización y diverge con el tiempo. Un helper único es la fuente de verdad.

### D6 — Cableado en `runFrameTick` y harness frame loop
- `runFrameTick` (`useExamProctoring.ts`) corre `detectObjects(frame)` (en un try/catch propio, degradación silenciosa: un fallo no rompe el examen) y pasa `objects` a `pipeline.onSignals`.
- El frame processor del harness (`frontend/src/screens/harness/frameProcessor.ts`) hace lo mismo para que el staff vea/registre los eventos de objeto.
- `detectObjects` corre a una cadencia razonable (puede compartir el tick de ~5 fps; si el costo lo exige, submuestrear cada 2 ticks). Decisión inicial: cada tick; medir y submuestrear solo si degrada fps.

## Risks / Trade-offs

- **[Costo de cómputo: 4º detector puede bajar fps en equipos modestos]** → El proyecto ya tiene degradación graceful (RN-GLB-03, `graceful-degradation`). `detectObjects` es el primer candidato a submuestrear (cada 2 ticks) o bajar; un fallo en `detectObjects` se traga en silencio y no interrumpe Face/Pose ni el examen.
- **[Falsos positivos de Object Detection: el modelo confunde objetos (una taza ≈ algo)]** → Umbral de confianza conservador (0.5) + N frames consecutivos + lista de labels acotada. Y, sobre todo, L2.5: es señal para revisión humana, nunca sanción. El backend re-infiere server-side antes de cualquier peso forense.
- **[El label del modelo no mapea 1:1 al español/negocio]** → La lista `prohibited_object_labels` usa los labels crudos del modelo (inglés COCO); el payload guarda `etiqueta` cruda y la UI la traduce vía un mapa de display si hace falta. Documentado como deuda menor.
- **[Alguien cablea `VisionOverlay` en el examen y reintroduce puntos sobre la cara]** → La spec lo prohíbe explícitamente (escenario normativo) y se deja comentario-guardia en `useExamProctoring`. Test de regresión: el examen no instancia `VisionOverlay`.
- **[Modelo nuevo aumenta el peso de assets self-hosted]** → `object_detector.task` (~6 MB EfficientDet-Lite0) se sirve desde `/mediapipe/` como los demás, fuera del bundle JS inicial (no afecta el objetivo <500 KB del bundle). Se añade al script de descarga.
- **[Backend slim no valida el nuevo `tipo`]** → Aceptado: el slim trata `tipo` como string; el evento persiste y se re-infiere en el backend completo (C-12/C-24). Sin breaking change.

## Migration Plan

1. Añadir tipos + `detectObjects` a `VisionEngine` (interfaz) y al stub `MediaPipeVisionEngine` (devuelve vacío) → no rompe consumidores existentes.
2. Descargar `object_detector.task` (script `scripts/download-mediapipe-models.*`) y cargarlo en `RealMediaPipeVisionEngine`.
3. Extender `FrameSignals` + `TransitionConfig` + `evalObjects` en `stateTransitionRules.ts` (campos opcionales → retrocompatible).
4. Cablear `detectObjects` en `runFrameTick` (examen) y `frameProcessor` (harness).
5. Añadir `objeto_prohibido_detectado` a `TipoEvento` + `TIPO_EVENTO_LABEL` + `descripcionEvento`.
6. Limpiar `VisionOverlay` (sin mesh verde default; 468 opt-in) y ajustar copy del toggle.
7. Extraer helper `face_count` humano y aplicarlo en `EventLog`, `EventoCard`, `VisionSignalsPanel`.
8. Tests: regla `evalObjects` (sostenido, de-dup, ruido), stub devuelve vacío, overlay no dibuja mesh por default, examen no monta overlay, fraseo de `face_count`.

**Rollback**: todos los cambios son aditivos y de presentación. Revertir = quitar el detector del cableado (las señales `objects` opcionales se ignoran) y restaurar el render previo del overlay. Sin migración de datos.

## Open Questions

- ¿Cadencia final de `detectObjects` (cada tick vs cada 2 ticks)? Resolver midiendo fps en el harness con el modelo real antes de fijar el default.
- ¿Lista canónica de `prohibited_object_labels` por institución? Default conservador propuesto (`cell phone`, `book`, `laptop`); confirmar con el dueño/Acuerdo de Nivel de Proctoring si suma `remote`, `tv`, `keyboard`.
- ¿El staff quiere conservar un mesh "ligero" (68 pts) bajo otro toggle, o el 468 opt-in alcanza? Decisión actual: solo 468 opt-in; el código del subconjunto queda pero sin uso por default.
