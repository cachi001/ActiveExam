## 1. Ruta y navegación (admin-detection-test-harness)

- [ ] 1.1 Agregar entrada `{ to: '/admin/detection-test', icon: 'bug_report', label: 'Test de detección' }` al final de `STAFF_NAV` en `frontend/src/ui/nav.ts`
- [ ] 1.2 Verificar cuál es el guard de roles del router admin existente y confirmar que protege `/admin/detection-test` para `admin_examenes` | `coordinador`; agregar la ruta al router apuntando a `AdminDetectionHarness` lazy-imported
- [ ] 1.3 Done observable: navegar a `/admin/detection-test` como admin muestra la pantalla; como alumno/rol sin permiso redirige al login o acceso denegado

## 2. Scaffold del componente AdminDetectionHarness (admin-detection-test-harness)

- [ ] 2.1 Crear `frontend/src/screens/AdminDetectionHarness.tsx` con estructura base: header con badge "MODO DIAGNÓSTICO — sin examen real", estado `idle | initializing | running | stopped`, botón "Iniciar cámara" / "Detener"
- [ ] 2.2 Implementar `getUserMedia` + bucle de frames (`requestAnimationFrame` o `setInterval` según fps objetivo) que capture `ImageBitmap` del `<video>` element y lo pase al engine
- [ ] 2.3 Done observable: el componente renderiza sin errores en `/admin/detection-test`; al hacer clic en "Iniciar cámara" el browser pide permisos de cámara

## 3. Instanciación del motor y pipeline (admin-detection-test-harness)

- [ ] 3.1 Instanciar `MediaPipeVisionEngine` y llamar a `engine.init()` al iniciar la sesión del harness; llamar a `engine.dispose()` al detener
- [ ] 3.2 Implementar `LocalHarnessEventSink` (interfaz `EventSink` de `visionPipeline.ts`) que: (a) llama a `store.pushAnomalia()` mapeando `DiscreteEvent` → `EventoSesion`, (b) acumula en array local con resultado ok/error, (c) NO instancia `StudentEventChannel`; agregar comentario explícito de restricción
- [ ] 3.3 Instanciar `VisionPipeline` con el motor, `LocalHarnessEventSink` y `StateTransitionRules` con config actual; pasar frames del bucle a `pipeline.onFrame()`
- [ ] 3.4 Done observable: con cámara activa, el motor corre en background; los eventos de reglas llegan al `LocalHarnessEventSink` sin ningún request HTTP/WS al backend

## 4. Panel de señales crudas (admin-detection-test-harness)

- [ ] 4.1 En cada frame, extraer del motor las señales crudas: `detectFaces` → `FaceDetectionSignal` (face_count, faces[]), `detectFaceMesh` si face_count >= 1 → gaze xy; indicar si keypoints de pose están disponibles
- [ ] 4.2 Renderizar panel "Señales crudas" con: contador de rostros, tabla de bounding boxes (x, y, width, height, confidence), vector gaze (x, y), indicador de pose; actualizar por cada frame
- [ ] 4.3 Done observable: con un rostro frente a la cámara el panel muestra face_count=1, una bounding box y el gaze; sin rostro muestra "Sin rostro detectado"

## 5. Panel de configuración de umbrales (admin-detection-test-harness)

- [ ] 5.1 Renderizar sección "Configuración de umbrales" con un input numérico por cada campo de `TransitionConfig` (`face_absent_ms`, `multiple_faces_frames`, `gaze_deviation_threshold`, `gaze_sustained_ms`, `gaze_fixation_tolerance`) inicializado con `DEFAULT_CONFIG`
- [ ] 5.2 Al cambiar un valor válido: recrear el `VisionPipeline` con la nueva instancia de `StateTransitionRules` (motor existente, mismo sink) para el siguiente frame; mostrar mensaje de validación inline para valores inválidos (no numérico o negativo)
- [ ] 5.3 Implementar botón "Resetear estado" que reinstancie `StateTransitionRules` con el config actual sin detener el stream
- [ ] 5.4 Done observable: cambiar `face_absent_ms` a 500ms y alejar la cara de la cámara por 0.5s dispara el evento `rostro_ausente` más rápido; el botón "Resetear estado" limpia el historial de ausencia sin interrumpir el video

## 6. Log de eventos y verificación del sink (detection-event-verification)

- [ ] 6.1 Mantener en estado local un array de entradas de log `{ event: DiscreteEvent, sinkStatus: 'ok' | 'error', sinkError?: string, inStore: boolean, loggedAt: number }` con límite de 200 entradas; mostrar aviso si se trunca
- [ ] 6.2 Renderizar lista ordenada (más reciente primero) con: tipo, severidad (badge coloreado), ts relativo, payload colapsable, flag `trigger_evidence`, indicador sink (✓/✗), indicador "en store"
- [ ] 6.3 Mostrar el mensaje "Sin eventos aún — señales dentro de umbrales" cuando la lista está vacía y han pasado más de 10 segundos desde el inicio de la sesión
- [ ] 6.4 Done observable: cubrir la cámara por 3+ segundos (con `face_absent_ms` default) dispara `rostro_ausente`; la entrada aparece en el log con severidad="media", sink=✓, inStore=true

## 7. Contador de store y overflow (detection-event-verification)

- [ ] 7.1 Mostrar contador en tiempo real: "X eventos en store.anomaliasVivo (límite 50)"; leer directamente de `useApp(s => s.anomaliasVivo.length)`
- [ ] 7.2 Cuando se produce overflow (store ya tiene 50 y llega uno nuevo), marcar la entrada del log correspondiente con badge "store: overflow, evento anterior descartado"
- [ ] 7.3 Done observable: generar 51 eventos en el harness (bajar `face_absent_ms` y tapar/destapar la cámara repetidamente) muestra el badge de overflow en la entrada 51

## 8. Filtro por severidad y exportación (detection-event-verification)

- [ ] 8.1 Implementar multi-select de severidades (baseline, baja, media, alta, critica) que filtre el log sin borrar el historial; mostrar "N eventos (M visibles)" cuando el filtro está activo
- [ ] 8.2 Implementar botón "Exportar log" que genere un Blob JSON con `{ session_start_ts, config: TransitionConfig, events: DiscreteEvent[] }` y lo descargue como `detection-harness-log-<ISO timestamp>.json`; mostrar toast si el array de eventos está vacío
- [ ] 8.3 Done observable: filtrar por "alta" muestra solo `multiples_rostros` y `monitor_adicional`; exportar descarga un JSON válido parseable con `JSON.parse()`

## 9. Verificación final e integración

- [ ] 9.1 Verificar que ningún import en `AdminDetectionHarness.tsx` referencia `StudentEventChannel`, `ResilientStudentEventChannel` ni ningún endpoint del API backend
- [ ] 9.2 Verificar que el flujo del alumno (`Examen.tsx`) no fue modificado y sus tests existentes siguen pasando
- [ ] 9.3 Done observable: `openspec validate c-23-admin-mediapipe-test-harness --strict` devuelve 0 errores; la pantalla funciona end-to-end con cámara real
