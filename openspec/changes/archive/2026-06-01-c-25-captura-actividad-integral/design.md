# Design — c-25 Captura de actividad integral (visión + navegador) y validación end-to-end

## Contexto y objetivo

La base funcional del proctoring es capturar y REGISTRAR toda actividad sospechosa durante un examen, y poder VALIDARLA end-to-end con una persona real. La visión ya está cableada; falta completar los detectores de navegador/entorno y hacer que la página de testeo cubra TODO (no solo visión).

Principios de diseño que se respetan (no negociables):

- **L2.5 — nunca sanciona**: detectores producen SEÑALES; `stateTransitionRules` produce EVENTOS con severidad; ninguna transición deriva una sanción. El score prioriza, no juzga.
- **Cliente = sensor no confiable**: estos eventos se firman/re-validan server-side (C-10/C-12). El front solo capta y reporta.
- **DD-17 / abstracción**: el pipeline depende de interfaces; los detectores de contexto se inyectan (`doc`, `win`, providers) para testear sin navegador real, igual que `contextDetectors.ts` hoy.
- **Aislamiento del harness (C-23, D-4)**: la página de testeo usa un `EventSink` local "air-gapped", sin tocar el backend de producción.

## Inventario: EXISTE vs FALTA

### Visión (pipeline de detección)

| Pieza | Estado | Ubicación / nota |
|---|---|---|
| `VisionEngine` (interfaz abstracta) | EXISTE | `frontend/src/vision/VisionEngine.ts` |
| `MediaPipeVisionEngine` (Face Detection, Face Mesh, Pose) | EXISTE | `frontend/src/vision/MediaPipeVisionEngine.ts` |
| Liveness / gaze | EXISTE | `frontend/src/vision/liveness.ts`, `gaze.test.ts` |
| Pipeline `onFrame` → reglas → `EventSink` | EXISTE | `frontend/src/proctoring/visionPipeline.ts` |
| Reglas de transición (rostro ausente, múltiples rostros, mirada desviada) | EXISTE | `frontend/src/proctoring/stateTransitionRules.ts` |
| Eventos visión: `rostro_ausente` (media), `multiples_rostros` (alta, trigger_evidence), `mirada_desviada_sostenida` (media) | EXISTE | `stateTransitionRules.ts` |
| Gestos/pose como evento discreto propio | PARCIAL/FALTA | `MediaPipeVisionEngine.detectPose` existe; el harness muestra "pose disponible" pero NO hay regla que emita un evento de pose/gesto. Fuera de scope estricto de C-25 salvo exponer la señal; se documenta como gap. |

### Navegador / entorno (detección de actividad)

| Actividad sospechosa | Detector | Señal | Evento discreto | Estado |
|---|---|---|---|---|
| Pérdida de foco de ventana (blur) | `FocusDetector` (blur/focus) | `focus_lost` | `perdida_de_foco` (baja) | EXISTE |
| Pestaña deja de estar visible (visibilitychange) | `FocusDetector` (visibilitychange) | `focus_lost` | `perdida_de_foco` (baja) | EXISTE pero **mezclado**: hoy "cambio de pestaña" colapsa en `perdida_de_foco`. FALTA un tipo propio `cambio_pestana`. |
| Abrir/cambiar a otra pestaña | — | — | `cambio_pestana` (media) | FALTA tipo discreto propio |
| Monitores múltiples | `detectExtraMonitor` (getScreenDetails) | `extra_monitor` | `monitor_adicional` (alta) | Detector EXISTE; **NO cableado**: en `Examen.tsx:77` y en el harness `extra_monitor` está hardcodeado `false`. FALTA cablearlo. |
| Salida de pantalla completa | — | — | `salida_pantalla_completa` (media) | FALTA detector, señal, tipo y regla |
| Copy / Paste en el examen | — | — | `copiar_pegar` (media) | FALTA detector, señal, tipo y regla |

Búsquedas que confirman el inventario:
- `requestFullscreen/fullscreenchange`: solo `EquipmentCheck.tsx` usa `getScreenDetails` para un chequeo previo; **no** hay listener de `fullscreenchange` en el pipeline de examen.
- `clipboard/copy/paste`: sin resultados en `frontend/src` para detección de proctoring.
- `FocusDetector` se consume en `Examen.tsx` (flujo alumno) con `extra_monitor: false` fijo; `detectExtraMonitor` no se invoca en el flujo de examen.

### Tipos de evento del dominio (`TipoEvento`)

EXISTE (`frontend/src/lib/types.ts`): `rostro_ausente | multiples_rostros | mirada_desviada_sostenida | perdida_de_foco | monitor_adicional | corte_conectividad_prolongado`.

FALTA agregar: `cambio_pestana`, `salida_pantalla_completa`, `copiar_pegar`. Deben reflejarse también en `DESC_EVENTO`, `TIPO_EVENTO_LABEL` y `DETECTORES_DEFAULT` de `frontend/src/lib/api.ts`, y ser consistentes con el `event-schema-contract` de C-10 (que ya enumera "cambio de pestaña/pérdida de foco, monitor adicional" en su catálogo de tipos).

### Página de testeo (C-23 `AdminDetectionHarness`)

| Capacidad | Estado |
|---|---|
| Ruta protegida `/admin/detection-test`, modo diagnóstico, sink local air-gapped | EXISTE |
| Cámara real + señales crudas (face_count, bbox, gaze, pose) | EXISTE |
| Config de umbrales en vivo, reset de estado | EXISTE |
| Log de eventos: captura + confirmación de `EventSink` + reflejo en `store.anomaliasVivo`, filtro por severidad, export | EXISTE |
| Validación de **acciones de navegador** (foco, pestaña, fullscreen, copy/paste, monitores) | **FALTA** — el loop inyecta `focus_lost: false, extra_monitor: false` (`AdminDetectionHarness.tsx:376`) |
| Checklist de **cobertura integral** (cada tipo de actividad capturado al menos una vez) | FALTA |

## Decisiones de diseño

1. **Detectores de contexto bajo la misma abstracción inyectable.** Se amplía `contextDetectors.ts` con `FullscreenDetector`, `TabChangeDetector` (o se enriquece `FocusDetector` para distinguir pestaña vs ventana) y `ClipboardDetector`, todos con deps inyectables (`doc`/`win`) para tests sin navegador. La señal de monitor (`detectExtraMonitor`) se cablea como provider opcional; donde el navegador no permite getScreenDetails, devuelve `null` (no se puede determinar) sin abortar — comportamiento ya implementado.

2. **`FrameSignals` se extiende, no se rompe.** Se agregan campos opcionales (`tab_changed?`, `fullscreen_exited?`, `clipboard_action?`) a `FrameSignals`. Las reglas para eventos de navegador son discretas e instantáneas (no requieren umbral temporal sostenido como rostro/mirada): se emiten en el frame en que la señal está presente, con de-dupe básico para no spamear (p. ej. una salida de fullscreen = un evento hasta volver a entrar). Esto evita falsos positivos por repetición sin sancionar.

3. **Severidades por defecto conservadoras** (alineadas a RN-EV-04 y al patrón existente): `cambio_pestana` = media, `salida_pantalla_completa` = media, `copiar_pegar` = media, manteniendo `perdida_de_foco` = baja y `monitor_adicional` = alta. Ninguna dispara sanción; `monitor_adicional` ya existía como alta. Las severidades son configurables por institución a futuro (no en este change).

4. **El harness se extiende, no se reescribe.** Se cablea un set de detectores de contexto al harness (en lugar de `false` fijos), un panel "Señales de entorno" en vivo, y un checklist de cobertura que marca cada `tipo` del catálogo cuando aparece al menos una vez en el log. El sink local sigue siendo air-gapped (D-4): nada se envía al backend de producción.

5. **Catálogo como contrato.** Se declara una capability `suspicious-activity-catalog` que fija el mapa actividad→tipo→severidad. Es la fuente de verdad para `TipoEvento`, los labels y el checklist de cobertura del harness. Debe ser un subconjunto/compatible del catálogo del `event-schema-contract` de C-10.

## Alternativas consideradas

- **Reusar `perdida_de_foco` para cambio de pestaña** (no agregar `cambio_pestana`): descartado — el pedido exige distinguir "abrir/cambiar de pestaña" como actividad propia, y el revisor humano necesita la distinción semántica. Mantener `perdida_de_foco` para blur de ventana y agregar `cambio_pestana` para visibilidad de pestaña.
- **Página de testeo nueva en vez de extender C-23**: descartado — C-23 ya tiene sink air-gapped, log con confirmación de registro, filtros y export; extenderlo evita duplicar y mantiene una sola superficie de validación integral.
- **Detección de clipboard vía Clipboard API (lectura de contenido)**: descartado por privacidad/permiso — basta con detectar el *evento* `copy`/`paste` (que ocurrió), no su contenido. Cliente no confiable: el contenido no es evidencia válida igual.

## Dependencias

- **C-10** `event-ingestion-transport` / `event-schema-contract`: define `tipo`/`severidad` del dominio; los nuevos tipos deben ser compatibles.
- **C-11** `vision-engine-detectores`: provee `browser-context-detectors`, `state-transition-rules`, `vision-engine-abstraction` que este change extiende vía deltas `MODIFIED`.
- **C-23** `admin-mediapipe-test-harness`: provee el harness que se extiende.

## Riesgos

- **getScreenDetails requiere permiso** (Window Management): en muchos navegadores/contextos no está disponible o pide permiso. La señal `extra_monitor` debe degradar a "no determinable" sin romper (ya implementado). El checklist de cobertura debe marcar este caso como "no testeable en este navegador" en vez de fallar.
- **Fullscreen/copy-paste dependen del DOM real**: por eso se mantienen los detectores inyectables y se testean con dobles de `doc`/`win` (sin mocks de DB; estos son del navegador, no de la base).
