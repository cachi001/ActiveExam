# Design — C-11 `vision-engine-detectores`

> Diseño técnico del **pipeline de visión del cliente** (frontend / Web Worker). Produce las señales y, vía reglas de transición, los eventos discretos con severidad que C-10 ingesta. El motor de visión está abstraído (DD-17). La IA NO decide fraude ni sanciona (L2.5).

## Context

El procesamiento es **client-heavy** (DD-02): la visión corre en el navegador del estudiante porque centralizar ~2.100 streams sería 10–50× más caro. El stack frontend (React + Zustand) organiza el pipeline en `frontend/src/vision/` (motor abstraído + Web Worker) y `frontend/src/proctoring/` (detectores de contexto, reglas). MediaPipe es el motor del MVP, pero detrás de una interfaz para migrar a ONNX Runtime Web sin reescribir (DD-17), porque Google ha deprecado partes de MediaPipe repetidamente.

**Constraints duras del dominio**:
- La **IA no decide fraude** (RN-EV-01): produce señales; una capa de reglas de transición las convierte en eventos con severidad. Ninguna señal aplica sanción automática (L2.5, RN-RV-07).
- Los **falsos positivos son el riesgo** (RN-SC-05): umbrales conservadores, reglas configurables por institución (RN-EV-03), el filtro humano es estructural.
- **Detección probabilística y honesta**: no detecta una segunda computadora fuera de cuadro, un cómplice susurrando, conocimiento memorizado (`11_ia_y_vision.md`).
- **Degradación graceful, nunca abort silencioso** (RN-GLB-02, RN-GLB-03).
- El motor consume y produce contra el **contrato de evento de C-10** (no lo redefine).

**Stakeholders**: estudiante (en cuyo navegador corre el Web Worker), proctor (recibe alertas), institución (configura reglas/umbrales), y los downstream C-12 (evidencia disparada por evento severo) y C-13 (scoring).

## Goals / Non-Goals

**Goals:**
- Abstraer el motor de visión detrás de `VisionEngine` (MediaPipe MVP, ruta a ONNX Runtime Web).
- Ejecutar los tres detectores (Face Detection, Face Mesh, Pose) en un Web Worker con WASM+WebGL y buffers sin copias.
- Detectar el contexto del navegador (pestaña, foco, monitores).
- Convertir señales continuas en eventos discretos con severidad vía **reglas de transición configurables**, evitando falsos positivos por ruido.
- Disparar evidencia + alerta < 500 ms para múltiples rostros.
- Degradar graceful ante hardware insuficiente.

**Non-Goals:**
- NO redefinir el contrato de evento ni el transporte (es de C-10; este change produce eventos conformes).
- NO implementar la verificación biométrica de identidad inicial (otro change); aquí Face Mesh solo **produce** el embedding que la verificación silenciosa continua consume.
- NO implementar la captura/firma/cadena de custodia de evidencia (C-12); aquí solo se **dispara** el pedido de evidencia.
- NO implementar el scoring (C-13) ni el panel (C-15).
- NO aplicar ninguna sanción ni decisión de fraude (L2.5).

## Decisions

### D1 — Motor de visión detrás de la interfaz `VisionEngine` (DD-17)
**Decisión**: toda interacción con los modelos pasa por `VisionEngine`; MediaPipe es una implementación, ONNX Runtime Web la ruta. Reglas y transporte no referencian MediaPipe.
**Por qué**: Google deprecó partes de MediaPipe repetidamente; la abstracción evita reescribir el pipeline al migrar (DD-17).
**Alternativa considerada**: usar MediaPipe directo en las reglas → acopla todo el pipeline a un motor inestable.

### D2 — Inferencia en Web Worker con WASM+WebGL y transferencia de buffers sin copias
**Decisión**: los detectores corren en un Web Worker dedicado; los buffers de pixels se transfieren (transferables) sin copia entre el hilo principal y el worker.
**Por qué**: no bloquear el hilo principal (UI del examen) ni duplicar memoria de frames; permite los fps objetivo en hardware modesto (`11_ia_y_vision.md`).
**Alternativa considerada**: inferencia en el hilo principal → congela la UI y baja los fps.

### D3 — Las reglas de transición son una capa separada del motor, configurable por institución
**Decisión**: las señales continuas del motor entran a una capa de reglas (umbrales temporales, fotogramas consecutivos, patrones) que produce los eventos discretos con severidad; los parámetros son configurables por institución (RN-EV-03).
**Por qué**: separa "qué ve el modelo" de "qué constituye un evento", que es una decisión institucional y calibrable; evita falsos positivos por ruido (RN-EV-02) sin tocar el motor.
**Alternativa considerada**: emitir un evento por cada señal del modelo → falsos positivos masivos por ruido instantáneo.

### D4 — Umbrales conservadores por defecto; el filtro humano es estructural
**Decisión**: los umbrales del MVP son conservadores (minimizan falsos positivos); las reglas no producen veredictos, solo señales que alimentan score y panel.
**Por qué**: a 700 estudiantes un 2% de falsos positivos son ~14 acusaciones injustas; la calibración prioriza minimizar falsos positivos y deja la recuperación de verdaderos positivos a la revisión humana (RN-SC-05).
**Alternativa considerada**: umbrales agresivos → más detección, pero acusaciones injustas que el sistema no debe producir.

### D5 — Degradación graceful escalonada, nunca abort silencioso
**Decisión**: ante hardware insuficiente, bajar Pose → Face Mesh → escalar a proctor; nunca abortar el examen en silencio (RN-GLB-02, RN-GLB-03).
**Por qué**: el dispositivo del estudiante no se controla; abortar silenciosamente penaliza injustamente a quien tiene hardware modesto.
**Alternativa considerada**: abortar si no corren los tres detectores → penaliza al estudiante por su hardware.

## Arquitectura del pipeline (frontend / Web Worker)

```
[Hilo principal — React]                 [Web Worker — vision]
  feed de cámara ──transfer buffer──►  VisionEngine (interfaz)
                                          ├─ MediaPipe (MVP)  [ruta → ONNX Runtime Web]
                                          ├─ Face Detection (5–10 fps) → bboxes + confianza
                                          ├─ Face Mesh (5–10 fps)      → mirada (iris) + embedding
                                          └─ Pose (2–5 fps)            → postura
            señales continuas ◄──────────┘
                  │
  [proctoring — detectores de contexto]   pestaña / foco / monitores
                  │
                  ▼
  [reglas de transición configurables]  umbral temporal · fotogramas · patrón sostenido
                  │  evento discreto + severidad (conforme al contrato de C-10)
                  ▼
  [transport — C-10]  WS estudiante (firma + ingesta)   ──► múltiples rostros: evidencia (C-12) + alerta <500ms
                  │
  [degradación graceful]  baja Pose → Face Mesh → escala a proctor (nunca abort silencioso)
```

| Componente | Responsabilidad | Notas |
|------------|-----------------|-------|
| `VisionEngine` | abstracción del motor | MediaPipe MVP, ruta ONNX (D1) |
| Detectores de visión | señales de rostro/mirada/embedding/postura | Web Worker, WASM+WebGL, buffers sin copias (D2) |
| Detectores de contexto | pestaña/foco/monitores | API de visibilidad y de pantallas |
| Reglas de transición | señales → eventos con severidad | configurables por institución (D3), conservadoras (D4) |
| Degradación | bajar detectores / escalar | nunca abort silencioso (D5) |

## Risks / Trade-offs

- **[Atar el pipeline a MediaPipe]** → Mitigación: D1 — interfaz `VisionEngine`; ruta a ONNX Runtime Web.
- **[Falsos positivos por ruido]** → Mitigación: D3/D4 — reglas con umbrales temporales/fotogramas/patrones; umbrales conservadores; filtro humano estructural.
- **[Bloquear la UI del examen]** → Mitigación: D2 — inferencia en Web Worker con buffers transferibles sin copias.
- **[Penalizar al estudiante por hardware modesto]** → Mitigación: D5 — degradación graceful escalonada, nunca abort silencioso.
- **[Expectativas irreales sobre la detección]** → Mitigación: honestidad arquitectónica — la detección es probabilística y la IA no sanciona (L2.5); lo no detectable se documenta.
- **Trade-off aceptado**: minimizar falsos positivos sube los falsos negativos; se acepta porque la revisión humana y el análisis estadístico post-examen recuperan verdaderos positivos sin acusar injustamente.

## Migration Plan

No hay sistema previo. Puesta en marcha:
1. Definir la interfaz `VisionEngine` e implementarla con MediaPipe; dejar el contrato listo para una impl. ONNX.
2. Montar el Web Worker con WASM+WebGL y la transferencia de buffers sin copias; cablear los tres detectores a sus fps.
3. Implementar los detectores de contexto del navegador.
4. Implementar la capa de reglas de transición configurables y conectarla a las señales.
5. Cablear la emisión de eventos conformes al contrato de C-10 (incluido el disparo de evidencia + alerta < 500 ms para múltiples rostros).
6. Implementar la detección de capacidad y la degradación graceful.

**Rollback**: al ser frontend sin estado persistente propio, un fallo se revierte desactivando el detector afectado o degradando; el contrato de evento de C-10 no se ve afectado.

## Open Questions

Las que este change **cierra**:
- ¿Cómo se abstrae el motor para migrar MediaPipe → ONNX sin reescribir? → `vision-engine-abstraction`.
- ¿Cómo se evita el ruido instantáneo sin perder eventos sostenidos? → `state-transition-rules`.

Las que **quedan fuera** (otros changes):
- Validación de firma, persistencia y fan-out de los eventos producidos → C-10.
- Captura, hash, firma y cadena de custodia de la evidencia disparada → C-12.
- Verificación biométrica de identidad inicial (este change solo produce el embedding) → change de biometría.
- Scoring y panel → C-13 / C-15.
