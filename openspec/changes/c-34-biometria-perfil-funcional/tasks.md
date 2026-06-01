## 1. Loader lazy singleton para enrollment

- [x] 1.1 Crear `frontend/src/vision/enrollmentEngineLoader.ts` con variables privadas `_cachedEnrollmentEngine: VisionEngine | null` y `_enrollmentInitPromise: Promise<VisionEngine> | null`
- [x] 1.2 Implementar `loadEnrollmentEngine(): Promise<VisionEngine>` con el patrón de tres pasos: cache hit → promesa en vuelo → nueva carga (dynamic import de `RealMediaPipeVisionEngine`)
- [x] 1.3 Implementar manejo de error en `loadEnrollmentEngine`: limpiar `_enrollmentInitPromise` en fallo, NO asignar `_cachedEnrollmentEngine`, propagar el error original
- [x] 1.4 Implementar `disposeEnrollmentEngine(): Promise<void>`: limpiar ambas variables de módulo y llamar `dispose()` sobre la instancia cacheada (error silenciado en dispose)
- [x] 1.5 Verificar que el dynamic import usa `await import('./RealMediaPipeVisionEngine')` (sin import estático) para que Vite emita chunk separado

## 2. Evaluador de retos de liveness (lógica pura)

- [x] 2.1 Crear `frontend/src/vision/enrollmentChallengeDetector.ts` con las constantes de thresholds exportadas: `GAZE_TURN_THRESHOLD = 0.25`, `BLINK_CLOSE_THRESHOLD = 0.015`, `FACE_APPROACH_THRESHOLD = 0.55`, `SMILE_WIDTH_THRESHOLD = 0.12`, `FRAMES_MIN_TURN = 3`, `FRAMES_MIN_BLINK = 2`, `FRAMES_MIN_APPROACH = 3`, `FRAMES_MIN_SMILE = 3`
- [x] 2.2 Implementar `evaluateChallenge(challenge: ActiveChallenge, landmarks: FaceLandmark[], gaze: {x: number, y: number}, bbox: {width: number} | null): boolean` que retorna `true` si el frame actual cumple el threshold del reto (sin lógica de acumulación — eso es del componente)
- [x] 2.3 Implementar evaluación `girar_izquierda`: `gaze.x < -GAZE_TURN_THRESHOLD`
- [x] 2.4 Implementar evaluación `girar_derecha`: `gaze.x > GAZE_TURN_THRESHOLD`
- [x] 2.5 Implementar evaluación `parpadear`: distancia vertical `|landmarks[159].y - landmarks[145].y| < BLINK_CLOSE_THRESHOLD` (retorna `false` si `landmarks.length < 160`)
- [x] 2.6 Implementar evaluación `acercarse`: `bbox !== null && bbox.width > FACE_APPROACH_THRESHOLD`
- [x] 2.7 Implementar evaluación `sonreír`: distancia horizontal `|landmarks[291].x - landmarks[61].x| > SMILE_WIDTH_THRESHOLD` (retorna `false` si `landmarks.length < 292`)

## 3. Refactor del componente — estado y tipos

- [x] 3.1 Agregar estado `motorListo: boolean` (false mientras carga), `motorError: string | null`, `fallbackManual: boolean` (false por default) al componente `EnrollmentBiometricStep`
- [x] 3.2 Agregar `useRef` para: `rafHandleRef: number | null` (handle del RAF), `lastLandmarksRef: FaceLandmark[]` (landmarks del último frame), `challengeCountsRef: Map<ActiveChallenge, number>` (acumuladores de frames consecutivos por reto)
- [x] 3.3 Agregar estado `fullscreenActive: boolean` y `fullscreenFallback: boolean` para gestionar el modo fullscreen/fallback
- [x] 3.4 Agregar `containerRef: useRef<HTMLDivElement>` para el contenedor de captura (target de `requestFullscreen`)
- [x] 3.5 Tipar correctamente las importaciones nuevas: `FaceLandmark` de `VisionEngine`, `ActiveChallenge` de `liveness.ts`, `loadEnrollmentEngine`, `disposeEnrollmentEngine` de `enrollmentEngineLoader`

## 4. Refactor del componente — ciclo de vida del motor

- [x] 4.1 En `iniciarCaptura()`: llamar `loadEnrollmentEngine()` mostrando spinner (`motorListo = false`) antes de pasar a fase `capturando`; si resuelve, `motorListo = true` e iniciar el RAF loop; si rechaza, `motorError = err.message`
- [x] 4.2 Conectar el `useEffect` de cleanup del componente para llamar `disposeEnrollmentEngine()` al desmontarse (además de detener el stream de cámara existente)
- [x] 4.3 Cancelar el RAF loop (`cancelAnimationFrame(rafHandleRef.current)`) al cambiar de fase o desmontar

## 5. Refactor del componente — loop RAF y detección de retos

- [x] 5.1 Implementar `startDetectionLoop(engine: VisionEngine)` que arranca el loop RAF con `requestAnimationFrame(detectFrame)`
- [x] 5.2 En `detectFrame`: hacer `createImageBitmap(videoRef.current)` → `engine.detectFaceMesh(bitmap)` → `engine.detectFaces(bitmap)` → evaluar retos → `requestAnimationFrame(detectFrame)` (si la fase sigue siendo `capturando`)
- [x] 5.3 Actualizar `lastLandmarksRef.current` con los landmarks del frame si `face_count > 0`
- [x] 5.4 Por cada reto pendiente (no en `resueltos`): llamar `evaluateChallenge(reto, landmarks, gaze, bbox)` — si retorna `true`, incrementar el acumulador; si retorna `false`, resetear el acumulador a 0
- [x] 5.5 Si el acumulador del reto alcanza `FRAMES_MIN_*`, llamar `resolverReto(reto)` y resetear el acumulador
- [x] 5.6 Si `detectFaces` retorna `face_count === 0`, resetear todos los acumuladores sin marcar retos

## 6. Refactor del componente — embedding real

- [x] 6.1 En `procesarCaptura()`: reemplazar `Array.from({length:128}, () => Math.random()*2-1)` por `embeddingFromLandmarks(lastLandmarksRef.current)` (importar de `MediaPipeVisionEngine.ts`)
- [x] 6.2 Si `lastLandmarksRef.current.length === 0` al procesar, volver a fase `capturando` con mensaje "No se detectó tu cara, intentá de nuevo" en lugar de generar embedding vacío
- [x] 6.3 Agregar comentario inline documentando que el embedding tiene dimensionalidad `3 × nro_landmarks` (no 128) y que el backend de producción comprimirá via PCA/capa densa (OQ-1 del design)

## 7. Refactor del componente — fullscreen en móvil

- [x] 7.1 Implementar `isMobileOrTouch(): boolean` con `window.innerWidth < 768 || 'ontouchstart' in window || navigator.maxTouchPoints > 0`
- [x] 7.2 En `iniciarCaptura()`: si `isMobileOrTouch()`, llamar `containerRef.current?.requestFullscreen().catch(() => setFullscreenFallback(true))`; si `requestFullscreen` no existe en el elemento, llamar directamente `setFullscreenFallback(true)`
- [x] 7.3 Registrar listener `document.addEventListener('fullscreenchange', onFullscreenChange)` en el `useEffect` de montaje; en `onFullscreenChange`: si `document.fullscreenElement === null`, sincronizar `fullscreenActive = false` y `fullscreenFallback = false`
- [x] 7.4 En `procesarCaptura()` (al completar) y en el handler de cancelar: llamar `document.exitFullscreen?.()` y `setFullscreenActive(false)`, `setFullscreenFallback(false)`
- [x] 7.5 Aplicar clases condicionales al `containerRef`: cuando `fullscreenFallback` es `true`, agregar `fixed inset-0 z-50 bg-black flex flex-col items-center justify-center`; cuando es `false`, mantener el layout normal

## 8. Refactor del componente — UI modo fallback manual

- [x] 8.1 Cuando `motorError !== null` y `fallbackManual === false`: mostrar mensaje de error descriptivo y botón "Continuar sin detección automática" que setea `fallbackManual = true` y pasa a fase `capturando`
- [x] 8.2 Cuando `fallbackManual === true` y fase es `capturando`: mostrar botones de resolución manual (el comportamiento pre-C-34) con banner "Motor de visión no disponible — modo de prueba manual"
- [x] 8.3 Cuando `motorListo === false` y fase es aún `instrucciones` (cargando): mostrar spinner "Preparando verificación…" en lugar del botón "Iniciar captura"
- [x] 8.4 Cuando `motorListo === true` y fase es `capturando` con motor activo: no mostrar ningún botón de resolución manual

## 9. Actualizar CHANGES.md

- [x] 9.1 Agregar entrada `[C-34] c-34-biometria-perfil-funcional` en la sección "Refinamiento post-fundación" de `CHANGES.md` con estado `[ ]`, scope, dependencias y governance ALTO
- [x] 9.2 Actualizar el total en el resumen de CHANGES.md de "33 changes" a "34 changes"

## 10. Verificación

- [x] 10.1 Ejecutar `tsc --noEmit` desde `frontend/` y confirmar 0 errores de TypeScript
- [ ] 10.2 Verificar manualmente en Chrome desktop que los 5 retos se detectan por movimiento real de cara (no por botón)
- [ ] 10.3 Verificar que el embedding en el log del mock API ya no es `Math.random` (verificar que el vector tiene valores deterministas entre runs)
- [ ] 10.4 Verificar en Chrome mobile (DevTools device emulation) que al iniciar captura se activa el modo fullscreen o el fallback CSS
- [ ] 10.5 Verificar que al desmontar el componente (navegar a otra pantalla) no quedan errores en consola relacionados con RAF o dispose del motor
