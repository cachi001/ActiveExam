## 1. Tipos TypeScript de proctoring en `types.ts`

- [ ] 1.1 Agregar tipo `VeredictoReinferencia` como literal union: `'coincide' | 'discrepancia' | 'sin_referencia' | 'error'`
- [ ] 1.2 Agregar tipo `EventoProctoringDetalle` con campos: `evento_id`, `tipo`, `severidad`, `ts_cliente`, `payload?`, `screenshot_base64?`, `screenshot_sha256?`, `face_count_cliente?`, `veredicto_reinferencia?`, `face_count_servidor?`
- [ ] 1.3 Agregar tipo `BiometriaDetalle` con campos: `liveness_ok`, `retos_resueltos`, `resultado`
- [ ] 1.4 Agregar tipo `SesionProctoringResumen` con campos: `id`, `modo`, `etiqueta?`, `creada_en`, `total_eventos`, `total_discrepancias`, `score`
- [ ] 1.5 Agregar tipo `SesionProctoringDetalle` que extiende `SesionProctoringResumen` con campos adicionales: `eventos: EventoProctoringDetalle[]`, `biometria: BiometriaDetalle | null`
- [ ] 1.6 Exportar los nuevos tipos desde `types.ts`

## 2. Helper `captureVideoFrame` en `videoFrameCapture.ts`

- [ ] 2.1 Crear `frontend/src/lib/videoFrameCapture.ts` con función exportada `captureVideoFrame(videoEl: HTMLVideoElement, quality?: number): string | null`
- [ ] 2.2 Implementar la función: verificar `readyState >= 2` y dimensiones no nulas; retornar `null` si no hay frame válido
- [ ] 2.3 Crear canvas temporal con `videoEl.videoWidth × videoEl.videoHeight`, llamar `ctx.drawImage(videoEl, 0, 0)`, retornar `canvas.toDataURL('image/jpeg', quality ?? 0.7)`
- [ ] 2.4 Envolver en try/catch y retornar `null` en caso de cualquier excepción (sin propagar)
- [ ] 2.5 Verificar que el módulo no importa React, MediaPipe ni `CameraSnapshotCapture`

## 3. Métodos duales de proctoring en `api.ts`

- [ ] 3.1 Implementar `api.crearSesionProctoring(modo, etiqueta?, examId?)` — real: POST `/proctoring/sessions`; mock: `{ id: 'mock-session-' + Date.now(), creada_en: new Date().toISOString() }` con delay 200ms
- [ ] 3.2 Implementar `api.enviarEventoProctoring(sessionId, payload)` — real: POST `/proctoring/sessions/{sessionId}/events`; fallo o mock: retorna `null` sin propagar
- [ ] 3.3 Implementar `api.enviarBiometriaProctoring(sessionId, bio)` — real: POST `/proctoring/sessions/{sessionId}/biometria`; fallo o mock: retorna `{ ok: true }` con delay 150ms
- [ ] 3.4 Implementar `api.listarSesionesProctoring()` — real: GET `/proctoring/sessions`; mock: array de dos `SesionProctoringResumen` de ejemplo con datos plausibles
- [ ] 3.5 Implementar `api.getSesionProctoring(id)` — real: GET `/proctoring/sessions/{id}`; mock: `SesionProctoringDetalle` con al menos 3 eventos, veredictos variados y datos de biometría
- [ ] 3.6 Exportar los nuevos métodos en el objeto `api`
- [ ] 3.7 Exportar los nuevos tipos de proctoring desde `api.ts` (re-export desde `types.ts`)

## 4. Ajuste de `DEFAULT_CONFIG` en `stateTransitionRules.ts`

- [ ] 4.1 Cambiar `gaze_deviation_threshold` de `0.15` a `0.20` en `DEFAULT_CONFIG`
- [ ] 4.2 Cambiar `face_absent_ms` de `2000` a `3000` en `DEFAULT_CONFIG`
- [ ] 4.3 Actualizar el comentario JSDoc del `DEFAULT_CONFIG` para reflejar los nuevos valores y su justificación (reducción de falsos positivos con motor MediaPipe real)

## 5. Modo "Grabar sesión" en `AdminDetectionHarness.tsx`

- [ ] 5.1 Importar `captureVideoFrame` desde `../lib/videoFrameCapture`
- [ ] 5.2 Importar los métodos `crearSesionProctoring` y `enviarEventoProctoring` desde `../lib/api`
- [ ] 5.3 Agregar tipo local `RecordMode = 'idle' | 'recording' | 'stopped'` al componente
- [ ] 5.4 Agregar estado `recordMode: RecordMode` (init: `'idle'`) y `recordedEventCount: number` (init: 0)
- [ ] 5.5 Agregar `sessionIdRef = useRef<string | null>(null)` para mantener el sessionId estable en callbacks
- [ ] 5.6 Implementar `startRecording()`: llama `api.crearSesionProctoring('diagnostico', 'Harness diagnóstico')`, guarda el id en `sessionIdRef`, cambia `recordMode` a `'recording'`, resetea `recordedEventCount = 0`; en caso de error: toast de error y no cambia de modo
- [ ] 5.7 Implementar `stopRecording()`: cambia `recordMode` a `'stopped'`, limpia `sessionIdRef.current = null`, muestra toast con resumen "Grabación detenida — N eventos enviados"
- [ ] 5.8 Modificar `stopHarness()`: al detener el harness, si `recordMode === 'recording'` llamar `stopRecording()` antes de proceder
- [ ] 5.9 Modificar `onSinkEvent.current`: al final del callback, si `sessionIdRef.current` y `recordMode === 'recording'`, capturar screenshot con `captureVideoFrame(videoRef.current, 0.7)` y llamar `api.enviarEventoProctoring(...)` de forma fire-and-forget (async sin await bloqueante)
- [ ] 5.10 En el callback de envío del evento: si la respuesta no es null, agregar `veredicto_reinferencia` y `face_count_servidor` a la entrada del log; si es null agregar badge de error de red; en ambos casos incrementar `recordedEventCount`
- [ ] 5.11 Agregar UI: botón "Grabar sesión" visible cuando `harnessState === 'running' && recordMode === 'idle'`
- [ ] 5.12 Agregar UI: badge "● GRABANDO" + contador "N eventos grabados" + sessionId truncado cuando `recordMode === 'recording'`
- [ ] 5.13 Agregar UI: botón "Detener grabación" cuando `recordMode === 'recording'`
- [ ] 5.14 Modificar las entradas del log para mostrar badge visual cuando el evento fue grabado con éxito o falló con error de red

## 6. Store — `proctoringSessionId` global

- [ ] 6.1 Agregar campo `proctoringSessionId: string | null` al store Zustand (`frontend/src/lib/store.ts`) con valor inicial `null`
- [ ] 6.2 Agregar acción `setProctoringSessionId(id: string | null): void` al store
- [ ] 6.3 Exportar el tipo del slice correspondiente

## 7. Envío de biometría al backend slim

- [ ] 7.1 Identificar el punto de completitud de la verificación biométrica en `Biometria.tsx` (o el componente donde se registra el resultado final de liveness)
- [ ] 7.2 Al completar la verificación biométrica exitosamente, leer `proctoringSessionId` del store
- [ ] 7.3 Si `proctoringSessionId !== null`, llamar `api.enviarBiometriaProctoring(proctoringSessionId, { liveness_ok, retos_resueltos, resultado })` de forma fire-and-forget
- [ ] 7.4 Manejar el error silenciosamente (no bloquear el flujo de biometría si la red falla)

## 8. Vista `ProctoringRevisor` — lista de sesiones

- [ ] 8.1 Crear `frontend/src/screens/ProctoringRevisor.tsx` con `StaffShell` y `STAFF_NAV`
- [ ] 8.2 Implementar carga de sesiones con `api.listarSesionesProctoring()` en `useEffect`
- [ ] 8.3 Mostrar spinner mientras carga; mensaje "No hay sesiones grabadas aún" si la lista está vacía
- [ ] 8.4 Renderizar cada sesión con: id (truncado), modo como badge, etiqueta, fecha formateada, total_eventos, total_discrepancias, score
- [ ] 8.5 Al hacer clic en una sesión, navegar a `/admin/proctoring-sessions/{id}` (o setear en store si no hay router con params)
- [ ] 8.6 Usar `Card`, `Badge`, `SeverityBadge`, `SectionTitle` del design system; seguir el estilo visual de `Revisor.tsx`

## 9. Vista `ProctoringSessionDetail` — detalle de sesión

- [ ] 9.1 Crear `frontend/src/screens/ProctoringSessionDetail.tsx` con `StaffShell` y `REVISOR_NAV`
- [ ] 9.2 Cargar detalle con `api.getSesionProctoring(id)` donde `id` proviene del store o parámetro de ruta
- [ ] 9.3 Mostrar disclaimer L2.5 en banner inamovible en la parte superior
- [ ] 9.4 Mostrar metadata: id, modo, etiqueta, fecha, score con gauge de color (reusar lógica `gaugeColor`/`gaugeTextColor` del harness)
- [ ] 9.5 Renderizar lista de eventos: por cada evento mostrar tipo (TIPO_EVENTO_LABEL), severidad (SeverityBadge), ts_cliente formateado
- [ ] 9.6 Para cada evento con `screenshot_base64`: mostrar miniatura `<img>` (max-height 120px); al hacer clic expandir en overlay o modal ligero; si `screenshot_base64` es null mostrar "Sin captura"
- [ ] 9.7 Para cada evento mostrar `veredicto_reinferencia` con color semántico: `'coincide'` → success-container, `'discrepancia'` → error-container, resto → surface-container
- [ ] 9.8 Para cada evento mostrar `face_count_cliente` vs `face_count_servidor`; si difieren agregar badge "Discrepancia"
- [ ] 9.9 Mostrar sección de biometría: si `biometria !== null` mostrar `liveness_ok`, `retos_resueltos[]`, `resultado`; si null mostrar "Sin verificación biométrica registrada"
- [ ] 9.10 Agregar botón "← Volver" que navega a `/admin/proctoring-sessions`

## 10. Router — rutas de revisión de proctoring

- [ ] 10.1 Agregar ruta `/admin/proctoring-sessions` en `frontend/src/lib/router.tsx` con componente `ProctoringRevisor`
- [ ] 10.2 Agregar ruta `/admin/proctoring-sessions/:id` (o `/admin/proctoring-session-detail`) con componente `ProctoringSessionDetail`
- [ ] 10.3 Agregar ítem de navegación "Sesiones grabadas" en `STAFF_NAV` con ícono `video_library` y ruta `/admin/proctoring-sessions`
- [ ] 10.4 Verificar que ambas rutas son accesibles para roles `admin_examenes`, `coordinador` y `revisor` según el guard de roles existente

## 11. Validación y polish

- [ ] 11.1 Verificar que `openspec validate --strict` pasa sin errores
- [ ] 11.2 Verificar que en modo `USE_REAL_BACKEND=0` todos los nuevos métodos de `api.ts` retornan mock sin llamadas HTTP
- [ ] 11.3 Verificar que `ProctoringRevisor` carga en `/admin/proctoring-sessions` y muestra datos mock
- [ ] 11.4 Verificar que el harness en modo diagnóstico puro (sin grabar) se comporta igual que antes
- [ ] 11.5 Verificar que `captureVideoFrame` retorna `null` (no lanza) cuando el video no tiene frame activo
- [ ] 11.6 Revisar que no se imprime `screenshot_base64` en ningún `console.log` de los componentes nuevos
