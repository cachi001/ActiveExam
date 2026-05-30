# Proposal — C-11 `vision-engine-detectores`

> **Naturaleza del change**: núcleo de monitoreo en tiempo real, governance **ALTO**. Frontend / Web Worker. Es el **productor de señales** del pipeline: corre los modelos de visión en el navegador del estudiante, convierte señales continuas en eventos discretos con severidad vía reglas de transición configurables, y los entrega al canal de ingesta (C-10). La IA NO decide "fraude" ni sanciona: produce señales que una persona pondera (L2.5).

## Why

El procesamiento es **client-heavy** (DD-02): centralizar la inferencia de ~2.100 streams sería 10–50× más caro, así que la visión corre en el navegador. Pero Google ha reorganizado/deprecado partes de MediaPipe repetidamente (DD-17): atar el sistema a MediaPipe sin una abstracción es deuda técnica garantizada. Por eso el motor de visión debe estar **abstraído detrás de una interfaz**, con MediaPipe en el MVP y ruta a ONNX Runtime Web sin reescribir el resto.

Además, la regla de oro del dominio (RN-EV-01): **la IA no decide "fraude"** — produce señales continuas que una capa de **reglas de transición de estado** convierte en eventos discretos con severidad. Sin esas reglas (umbrales temporales, fotogramas consecutivos, patrones sostenidos), el ruido instantáneo (un parpadeo, mirar al techo para pensar) generaría falsos positivos masivos. A 700 estudiantes, un 2% de falsos positivos son ~14 acusaciones injustas por examen; por eso los umbrales son conservadores y las reglas configurables por institución (RN-EV-03, RN-SC-05).

Y la mecánica de ejecución importa: WASM + WebGL en un Web Worker dedicado con transferencia de buffers sin copias, para no bloquear el hilo principal ni saturar el dispositivo, con **degradación graceful** (baja Pose → Face Mesh → escala a proctor) cuando el hardware no da (RN-GLB-03).

## What Changes

Construye el **pipeline de visión del cliente** que produce los eventos que C-10 ingesta.

- **Motor de visión abstraído (DD-17)**: una interfaz `VisionEngine` detrás de la cual vive la implementación MediaPipe del MVP, con la ruta a ONNX Runtime Web preparada — el resto del pipeline (reglas de transición, transporte) NO conoce la implementación concreta.
- **Tres detectores de visión**: Face Detection / BlazeFace (5–10 fps — ausencia/múltiples rostros, baja confianza), Face Mesh (5–10 fps — dirección de la mirada por iris + embedding para verificación silenciosa continua) y Pose (2–5 fps — posturas de consulta). Ejecutan sobre **WASM + WebGL en un Web Worker** con transferencia de buffers de pixels **sin copias**.
- **Detectores de navegador adicionales**: pestaña activa, foco de ventana y monitores múltiples (API de pantallas donde el navegador lo permita).
- **Reglas de transición de estado (configurables por institución)**: convierten señales continuas en eventos discretos con severidad usando umbrales temporales, fotogramas consecutivos y patrones sostenidos (RN-EV-02, RN-EV-03). Ejemplos: rostro ausente solo si se sostiene > 3 s; mirada desviada solo si es un patrón sostenido hacia un punto fijo, no la mirada normal de pensar (RN-EV-06).
- **Múltiples rostros (≥2 durante N fotogramas)** → severidad **alta** + disparo de captura de evidencia (vía C-12) + alerta al panel en **< 500 ms** (RN-EV-04, vía el fan-out de C-10).
- **Degradación graceful (RN-GLB-03)**: ante hardware insuficiente, primero baja Pose, luego Face Mesh, y solo si sigue siendo insuficiente se escala a un proctor — **nunca abort silencioso** (RN-GLB-02).

**La IA NUNCA sanciona ni decide fraude (L2.5, RN-EV-01)**: todas las señales alimentan un score y un panel donde una persona pondera el contexto. La detección es probabilística y honesta sobre sus límites (no detecta una segunda computadora fuera de cuadro, un cómplice susurrando, conocimiento memorizado).

## Capabilities

### New Capabilities

- `vision-engine-abstraction`: la interfaz `VisionEngine` que abstrae el motor de visión (MediaPipe en MVP, ruta a ONNX Runtime Web) detrás de un puerto, de modo que el resto del pipeline no dependa de la implementación concreta (DD-17).
- `vision-detectors`: los tres detectores de visión (Face Detection, Face Mesh, Pose) ejecutando WASM+WebGL en un Web Worker con transferencia de buffers sin copias, a sus fps objetivo.
- `browser-context-detectors`: los detectores de contexto del navegador — pestaña activa, foco de ventana y monitores múltiples.
- `state-transition-rules`: las reglas de transición de estado configurables por institución que convierten señales continuas en eventos discretos con severidad (umbrales temporales, fotogramas consecutivos, patrones sostenidos), evitando falsos positivos por ruido.
- `graceful-degradation`: la degradación graceful ante hardware insuficiente (baja Pose → Face Mesh → escala a proctor), nunca abort silencioso.

### Modified Capabilities

(Ninguna — no existen specs de dominio previas en `openspec/specs/` que este change modifique. Este change consume el `event-schema-contract` de C-10 como dependencia, no lo modifica.)

## Impact

- **Dependencias entrantes**: `C-10` (consume el `event-schema-contract` para producir eventos firmados conformes, y el canal WS para entregarlos; el disparo de evidencia y la alerta < 500 ms viajan por el fan-out de C-10).
- **Bloquea (downstream)**: C-12 (la captura de evidencia se dispara desde el evento severo que este change produce — p. ej. múltiples rostros), C-13 (el scoring pondera estos eventos). El embedding de Face Mesh alimenta la verificación silenciosa continua (RN-BIO-06) que produce el evento crítico "posible cambio de identidad".
- **Actores/sistemas afectados**: estudiante (en cuyo navegador corre el Web Worker), proctor (recibe las alertas derivadas de las señales), institución (configura las reglas de transición y los umbrales).
- **Riesgo principal**: falsos positivos por reglas mal calibradas — mitigado por umbrales conservadores por defecto (RN-SC-05), reglas configurables y la honestidad arquitectónica de que la detección es probabilística y el filtro humano es estructural.
- **Decisión clave (DD-17)**: la abstracción del motor permite migrar MediaPipe → ONNX Runtime Web sin reescribir reglas ni transporte.
