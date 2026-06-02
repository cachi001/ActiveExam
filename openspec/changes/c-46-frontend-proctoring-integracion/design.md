## Context

El harness diagnóstico (`AdminDetectionHarness`) ya tiene cámara activa, pipeline de visión completo (MediaPipe), detectores de contexto (foco, fullscreen, portapapeles) y un `LocalHarnessEventSink` air-gapped. El backend slim C-45 expone cinco endpoints REST sin auth bajo `/api/v1/proctoring`. `api.ts` ya tiene la infraestructura dual-mode (`USE_REAL_BACKEND`, `realFetch`, fallback demo) usada por consentimiento y biometría. `CameraSnapshotCapture` resuelve la captura de un frame de `<video>` a canvas → base64 JPEG. `Revisor`/`SessionDetail` operan con datos mock en-memoria.

Restricciones:
- **Dual-mode obligatorio**: `USE_REAL_BACKEND=0` → mock completo; el sitio en Vercel no puede depender del backend.
- **No buildear, no commitear**: solo artefactos.
- **L2.5**: el score es acumulador de priorización, nunca veredicto. La decisión disciplinaria es siempre humana.
- **Ley 25.326**: los screenshots son dato sensible; no se loguean en consola ni se persisten en localStorage.
- **Cliente = sensor no confiable**: el veredicto de re-inferencia del servidor es la fuente de verdad (face_count_servidor + veredicto_reinferencia).
- **Aislamiento del harness (D-4)**: el modo diagnóstico sin red se preserva intacto. El modo "Grabar" es opt-in.

## Goals / Non-Goals

**Goals:**
- Cinco métodos duales en `api.ts` con tipos TypeScript calcados del backend C-45.
- Modo "Grabar sesión" en el harness: crea sesión → captura screenshot por evento → envía al backend → degradación a local si falla la red.
- Helper puro `captureVideoFrame` extraído como módulo independiente (no importa `CameraSnapshotCapture` completo).
- Envío de biometría al backend atado al `sessionId` de la sesión activa de proctoring.
- Vista de revisión real (`ProctoringRevisor` + `ProctoringSessionDetail`) que consume GET /sessions y GET /sessions/{id}.
- Ajuste fino de `DEFAULT_CONFIG` en `stateTransitionRules.ts` para reducir falsos positivos.

**Non-Goals:**
- Autenticación/Keycloak en el backend slim (C-45 no tiene auth, es by design).
- Integración con el canal de eventos de producción (StudentEventChannel, WebSocket, C-10).
- UI de creación de sesiones manuales (solo desde el harness en modo grabar).
- Paginación en la lista de sesiones (el backend devuelve todas; MVP).
- Evidencia de video (webm/mp4) — solo screenshots estáticos por evento.

## Decisions

### D1: Dual-mode en `api.ts` — patrón try/catch con fallback mock

El mismo patrón que `recordConsent`/`getConsentText`: `if (USE_REAL_BACKEND) { try { return realFetch... } catch { /* fallback */ } }`. Alternativa descartada: módulos separados (`api-real.ts` / `api-mock.ts`) — más código, más superficie de divergencia entre real y mock.

Los tipos de respuesta del backend C-45 se definen en `types.ts` bajo el namespace de proctoring (`SesionProctoringResumen`, `SesionProctoringDetalle`, `EventoProctoringDetalle`, `BiometriaDetalle`, `VeredictoReinferencia`). Calcados del OpenAPI del backend — no se inventan contratos.

### D2: `captureVideoFrame` como módulo propio

`CameraSnapshotCapture` es un componente React con UI completa (portal, states, flujo de confirmación). Importarlo solo para el `canvas.drawImage` arrastraría 200+ líneas de UI. En cambio, se extrae `captureVideoFrame(videoEl: HTMLVideoElement, quality?: number): string | null` en `frontend/src/lib/videoFrameCapture.ts` — función pura, sin React, reutilizable en el harness y en futuras capturas de evidencia. Internamente: `canvas.drawImage(videoEl, 0, 0)` + `canvas.toDataURL('image/jpeg', quality)`.

### D3: Estado de sesión activa en el harness como `useRef` + estado React

El `sessionId` de la sesión grabada se guarda en `useRef<string | null>` (no en estado React) para que el callback del sink siempre lea el valor actual sin recrear el sink. El estado visible al usuario (modo, contador de eventos enviados) sí va a `useState`. Alternativa descartada: Zustand store — innecesario para un `sessionId` local al componente.

### D4: Degradación de red en modo Grabar — "fire and forget con log local"

Si `enviarEventoProctoring` falla (timeout, 5xx, sin conexión), el evento se registra igual en el log local del harness y el diagnóstico continúa. El error de red se muestra como badge "⚠ sin red" en la entrada del log, no como toast bloqueante. Nunca se rompe el loop de frames ni se detiene el harness. Esto preserva el principio de aislamiento (D-4): la red es opcional, el diagnóstico es la función primaria.

### D5: Nuevas pantallas de revisión — `ProctoringRevisor` + `ProctoringSessionDetail`

Se crean dos componentes nuevos en `screens/` (no se modifica `Revisor`/`SessionDetail` existentes) para no mezclar el flujo mock de revisión académica con el flujo real de revisión de sesiones de proctoring. `ProctoringRevisor` lista sesiones del backend slim. `ProctoringSessionDetail` muestra el detalle completo con screenshots. Ambos reutilizan `Card`, `Badge`, `SeverityBadge`, `SectionTitle`, el patrón visual de `Revisor` (C-43) y los badges de `ReviewQueueItem`. La ruta se agrega al router bajo `/admin/proctoring-sessions`.

### D6: Biometría → backend slim — acoplamiento por contexto de sesión activa

El envío de biometría al backend (`POST /sessions/{id}/biometria`) se activa cuando: (a) la sesión activa de proctoring existe (hay un `sessionId`), y (b) el flujo de verificación biométrica (`Biometria.tsx` o el step correspondiente) completa exitosamente. El `sessionId` se expone en `store.ts` como estado mínimo (`proctoringSessionId: string | null`). Alternativa descartada: prop drilling del sessionId — la biometría y el harness no están en el mismo árbol de componentes.

### D7: Ajuste de DEFAULT_CONFIG en stateTransitionRules

Basado en observaciones del harness con el motor MediaPipe real: `gaze_deviation_threshold` de 0.15 a 0.20 (reducir falsos positivos de mirada), `face_absent_ms` de 2000 a 3000ms (dar más margen antes de disparar "rostro ausente"). Los valores son los únicos parámetros del `DEFAULT_CONFIG` que mostraron disparos espurios frecuentes en sesiones cortas de diagnóstico. El resto del `DEFAULT_CONFIG` se preserva. Los nuevos valores siguen siendo configurables por UI en el harness.

## Risks / Trade-offs

- **[Riesgo] El backend slim Railway puede estar inaccesible** → Mitigation: dual-mode garantiza fallback mock. El harness funciona igual sin red. El modo Grabar muestra badge de error por evento fallido pero no bloquea.
- **[Riesgo] Screenshots en base64 aumentan el payload por evento** → Mitigation: calidad JPEG 0.7 (no 0.85 del perfil), resolución capturada del `<video>` que ya corre a 5fps/480p. El backend C-45 ya acepta screenshot_base64 como campo opcional.
- **[Riesgo] face_count del cliente puede diferir del servidor por el momento de la inferencia** → Mitigation: la UI de revisión muestra explícitamente ambos valores (face_count_cliente vs face_count_servidor) con el veredicto_reinferencia del backend. El revisor humano tiene toda la información. Nunca se oculta la discrepancia.
- **[Riesgo] stateTransitionRules cambios de DEFAULT_CONFIG afectan Examen.tsx** → Mitigation: el cambio es solo en `DEFAULT_CONFIG`; los valores son sobreescribibles desde la UI del harness. `Examen.tsx` inicializa su pipeline sin leer `DEFAULT_CONFIG` directamente — usa el constructor con su propia config.
- **[Trade-off] ProctoringRevisor duplica estructura visual de Revisor** → A cambio, el flujo mock de revisión académica queda intacto para el demo, y la revisión real tiene su propia ruta sin contaminar el flujo existente.

## Migration Plan

1. Agregar tipos y métodos a `api.ts`/`types.ts` — aditivos, sin breaking changes.
2. Agregar helper `videoFrameCapture.ts` — nuevo archivo, sin impacto en existentes.
3. Modificar `AdminDetectionHarness` — el modo diagnóstico existente se preserva; se agrega estado/UI de modo grabar como extensión opcional.
4. Modificar `stateTransitionRules.ts` — solo `DEFAULT_CONFIG`, retrocompatible.
5. Modificar `store.ts` — agregar `proctoringSessionId` y su setter, campo nuevo.
6. Agregar `ProctoringRevisor`/`ProctoringSessionDetail` — nuevos archivos.
7. Agregar ruta `/admin/proctoring-sessions` en el router — aditivo.

Rollback: ningún paso modifica contratos existentes. Revertir es eliminar los archivos nuevos y deshacer la extensión del harness.

## Open Questions

- ¿La ruta `/admin/proctoring-sessions` debe protegerse con guard de rol (`admin_examenes | coordinador | revisor`)? Asumo sí (patrón de rutas admin existentes) pero requiere confirmar qué roles deben ver la revisión de sesiones del slim.
- ¿El envío de biometría al backend slim debe ser bloqueante (esperar respuesta) o fire-and-forget? Si es bloqueante y el backend está caído, ¿el flujo de biometría falla? Se recomienda fire-and-forget con log de error, consistente con D4.
