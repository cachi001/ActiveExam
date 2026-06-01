## Why

La captura y el registro de TODA la actividad sospechosa durante un examen es la base funcional del proctoring: sin ella, ningún flujo aguas abajo (scoring C-13, panel proctor C-15, cola de revisión C-16, evidencia C-12/C-24) tiene insumos. Hoy esa base está **incompleta y, sobre todo, no validable end-to-end**:

- La **visión** está cableada (C-11): `VisionEngine` → `visionPipeline.onFrame` → `stateTransitionRules` → `EventSink`, emitiendo eventos discretos con severidad (`rostro_ausente`, `multiples_rostros`, `mirada_desviada_sostenida`).
- Los **detectores de navegador/entorno** están a medias: `contextDetectors.ts` provee `FocusDetector` (visibilitychange/blur/focus) y `detectExtraMonitor` (getScreenDetails), y `stateTransitionRules` emite `perdida_de_foco` (baja) y `monitor_adicional` (alta). Pero **falta** la detección de **salida de pantalla completa** y de **copy/paste**, no hay un tipo de evento discreto que distinga "abrir/cambiar de pestaña" de la pérdida de foco genérica, y el detector de monitores **no está cableado en producción** (en `Examen.tsx` y en el harness `extra_monitor` está hardcodeado en `false`).
- La **página de testeo** existente `AdminDetectionHarness` (C-23) valida **solo visión**: en su loop de frames inyecta `focus_lost: false, extra_monitor: false`. No hay forma de que una persona valide, con su propia cámara, gestos y acciones de navegador, que TODO (visión + entorno) se capta y registra correctamente.

Esto deja la base funcional sin confirmación observable: los errores de cableado, umbrales o tipos de evento de navegador solo se descubrirían en una sesión real de examen.

## What Changes

- **Completar los detectores de navegador/entorno** detrás de la misma abstracción de `contextDetectors.ts`, produciendo SEÑALES (no veredictos) que alimentan `stateTransitionRules` y se emiten por el MISMO pipeline/`EventSink` que la visión:
  - **Cambio/apertura de pestaña** (Page Visibility) como señal y evento discreto propio (`cambio_pestana`), distinto de la pérdida de foco de ventana.
  - **Salida de pantalla completa** (`fullscreenchange` / `document.fullscreenElement`) → señal y evento (`salida_pantalla_completa`).
  - **Copy/paste** (`copy` / `paste` sobre el documento del examen) → señal y evento (`copiar_pegar`).
  - **Monitores múltiples**: cablear `detectExtraMonitor` (ya existente) al pipeline de producción y al harness, dejando de hardcodear `extra_monitor`.
- **Extender `stateTransitionRules`** para emitir los nuevos tipos de evento de navegador con severidad por defecto conservadora, sin filtrado temporal donde el evento es discreto e instantáneo (un `paste`, una salida de fullscreen), respetando que la regla SOLO flaggea y nunca sanciona (L2.5).
- **Página de validación integral**: extender `AdminDetectionHarness` (C-23) para correr TODO end-to-end con la persona del usuario — señales de visión (rostro / mirada / pose / gestos) Y acciones de navegador en vivo — cableando los detectores de contexto reales (en lugar de los stubs `false`), con un panel de "señales de entorno" en vivo, un checklist de cobertura ("cada tipo de actividad sospechosa fue capturado al menos una vez") y el log de eventos existente confirmando captura + registro por el `EventSink`.
- **Catálogo de actividad sospechosa** (visión + navegador) mapeado a tipo de evento y severidad, declarado como contrato y reflejado en `TipoEvento` (`frontend/src/lib/types.ts`) y sus labels/descripciones (`frontend/src/lib/api.ts`).

Toda evidencia sigue siendo re-validable server-side: el cliente es un sensor no confiable; estos detectores producen señales/eventos para registro y revisión humana, no decisiones.

## Capabilities

### New Capabilities

- `browser-activity-detectors`: Detectores de actividad de navegador/entorno (cambio/apertura de pestaña, salida de pantalla completa, copy/paste) que producen señales para `stateTransitionRules` y se emiten como eventos discretos por el mismo `EventSink` que la visión, sin sancionar.
- `suspicious-activity-catalog`: Catálogo canónico de actividad sospechosa (visión + navegador) que mapea cada tipo de actividad a un `tipo` de evento del dominio y a una severidad, alineado con el `event-schema-contract` de C-10.
- `integral-activity-validation`: Validación de cobertura end-to-end en la página de testeo: el operador confirma, con su propia persona y navegador, que CADA tipo de actividad sospechosa del catálogo se capturó y registró al menos una vez (checklist de cobertura sobre el log existente).

### Modified Capabilities

- `state-transition-rules` (C-11): se agregan las transiciones para los nuevos tipos de evento de navegador (cambio de pestaña, salida de pantalla completa, copy/paste), manteniendo la garantía de no-sanción.
- `browser-context-detectors` (C-11): se cablea el detector de monitores múltiples al flujo (deja de estar hardcodeado) y se incorporan los nuevos detectores de entorno bajo la misma abstracción inyectable.
- `admin-detection-test-harness` (C-23): el harness deja de inyectar `focus_lost/extra_monitor` fijos en `false` y cablea los detectores de contexto reales, sumando un panel de señales de entorno en vivo y el checklist de cobertura integral.

## Impact

- **Archivos modificados (producción de detección)**: `frontend/src/proctoring/contextDetectors.ts` (nuevos detectores de fullscreen, pestaña, copy/paste; señal de monitor cableable), `frontend/src/proctoring/stateTransitionRules.ts` (nuevas transiciones/tipos y `FrameSignals`), `frontend/src/screens/Examen.tsx` (cablear los detectores reales en el flujo del alumno, dejar de hardcodear `extra_monitor`).
- **Archivos modificados (catálogo/labels)**: `frontend/src/lib/types.ts` (`TipoEvento` +nuevos tipos), `frontend/src/lib/api.ts` (`DESC_EVENTO`, `TIPO_EVENTO_LABEL`, `DETECTORES_DEFAULT`).
- **Archivos modificados (página de testeo)**: `frontend/src/screens/AdminDetectionHarness.tsx` (cablear detectores de contexto reales, panel de entorno, checklist de cobertura).
- **Archivos nuevos**: specs bajo `openspec/changes/c-25-captura-actividad-integral/specs/` (capabilities nuevas) y deltas `MODIFIED` para las capabilities existentes.
- **Dependencias (uso, no modificación de sus specs propios)**: C-10 `event-schema-contract` (tipos/severidades del dominio), C-11 `vision-engine-abstraction` y `vision-detectors`, C-23 estructura del harness.
- **Reglas duras**: el sistema NO sanciona automático — flaggea y registra para revisión humana; el cliente es sensor no confiable, la evidencia se re-valida server-side; componentes React en PascalCase. No se buildea ni commitea en este change (solo propuesta).
