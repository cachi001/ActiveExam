## 1. Crear componente BiometricCapture — estructura y tipos

- [x] 1.1 Crear `frontend/src/ui/BiometricCapture.tsx` con el esqueleto del componente: importar `useCallback`, `useEffect`, `useRef`, `useState` de React; importar `loadEnrollmentEngine`, `disposeEnrollmentEngine` de `enrollmentEngineLoader`; importar `evaluateChallenge`, `framesMinForChallenge` de `enrollmentChallengeDetector`; importar `pickActiveChallenges`, `ACTIVE_CHALLENGES` de `liveness`; importar tipos `FaceLandmark`, `VisionEngine` de `VisionEngine`; importar `ActiveChallenge` de `liveness`; importar `DESAFIOS` de `lib/api`.
- [x] 1.2 Definir la interfaz `BiometricCaptureProps` con las props: `challenges?: ActiveChallenge[]`, `challengeCount?: number`, `contextLabel?: string`, `onComplete: (landmarks: FaceLandmark[]) => void`, `onCancel: () => void`.
- [x] 1.3 Definir el tipo `Fase = 'capturando' | 'error'` interno al componente.
- [x] 1.4 Declarar los refs del componente: `videoRef`, `containerRef`, `streamRef`, `rafHandleRef`, `engineRef`, `lastLandmarksRef`, `challengeCountsRef`, `faseRef`, `desafiosRef`, `resueltosRef`, `procesarCompletadoRef`.

## 2. Crear componente BiometricCapture — lógica de cámara y motor

- [x] 2.1 Implementar el `useEffect` de inicialización de cámara: `getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } })`, asignar stream al `videoRef`, manejar error con `setFase('error')` y mensaje, cleanup con `getTracks().forEach(t => t.stop())`.
- [x] 2.2 Implementar la carga del motor en el mismo `useEffect` de montaje (o un efecto separado): llamar `loadEnrollmentEngine()`, en éxito asignar a `engineRef` y `setMotorListo(true)`, en rechazo `setMotorError(msg)` y activar fallback manual.
- [x] 2.3 Implementar el listener `fullscreenchange` para sincronizar estado de fullscreen al desmontar.
- [x] 2.4 Implementar el cleanup del `useEffect`: cancelar RAF, llamar `disposeEnrollmentEngine()`, detener stream, quitar listener `fullscreenchange`.

## 3. Crear componente BiometricCapture — loop RAF de detección

- [x] 3.1 Implementar `startDetectionLoop(engine: VisionEngine)`: loop `requestAnimationFrame` que captura bitmap del video, llama `Promise.all([engine.detectFaceMesh(bitmap), engine.detectFaces(bitmap)])`, cierra el bitmap, extrae `landmarks`, `gaze`, `face_count`, `bbox`.
- [x] 3.2 Implementar lógica de evaluación por frame: si `face_count === 0`, limpiar `challengeCountsRef`; si hay cara, iterar retos pendientes, llamar `evaluateChallenge(id, landmarks, gaze, bbox)`, acumular frames consecutivos en `challengeCountsRef`, marcar resuelto cuando acumulador supere `framesMinForChallenge(id)`.
- [x] 3.3 Implementar `resolverRetoFromLoop(id)` con `setResueltos` updater funcional, verificar si todos resueltos y llamar `procesarCompletadoRef.current()` via `setTimeout(() => ..., 0)`.
- [x] 3.4 Asegurar que el loop se detiene cuando `faseRef.current !== 'capturando'`.

## 4. Crear componente BiometricCapture — lógica de completado y fullscreen

- [x] 4.1 Implementar `procesarCompletado()`: cancelar RAF, llamar `disposeEnrollmentEngine()`, salir de fullscreen si activo, llamar `onComplete(lastLandmarksRef.current)`.
- [x] 4.2 Registrar `procesarCompletado` en `procesarCompletadoRef` via `useEffect([procesarCompletado])`.
- [x] 4.3 Implementar `activarFullscreen()`: llamar `containerRef.current.requestFullscreen()` como best-effort, en rechazo o no disponible no lanzar error (el overlay CSS ya cubre la pantalla).
- [x] 4.4 Implementar `handleCancel()`: cancelar RAF, llamar `disposeEnrollmentEngine()`, salir de fullscreen, detener stream, llamar `onCancel()`.
- [x] 4.5 Implementar la inicialización de retos al montar: si `props.challenges` está definido usarlo, si no llamar `pickActiveChallenges(challengeCount ?? 2)`. Asignar a `desafios` state y `desafiosRef`.
- [x] 4.6 Implementar la lógica de activar fullscreen cuando el motor está listo y empezar el loop RAF: en el `useEffect` del motor, al resolver `loadEnrollmentEngine()`, llamar `activarFullscreen()` y `startDetectionLoop(engine)`.

## 5. Crear componente BiometricCapture — modo fallback manual

- [x] 5.1 Implementar `resolverRetoManual(id: string)` con `setResueltos` updater funcional (igual que `resolverRetoFromLoop` pero sin RAF).
- [x] 5.2 Asegurar que en fallback manual los botones de reto están habilitados y son clicables.
- [x] 5.3 Asegurar que al completar todos los retos en fallback, se llama `onComplete(lastLandmarksRef.current)` (puede ser array vacío).

## 6. Crear componente BiometricCapture — UI inmersiva

- [x] 6.1 Implementar el contenedor raíz del overlay: `<div ref={containerRef} className="fixed inset-0 z-50 bg-neutral-950 flex flex-col items-center justify-center">`.
- [x] 6.2 Implementar el botón cancelar discreto: posición `absolute top-4 right-4`, text-sm, opacidad reducida, llama `handleCancel`.
- [x] 6.3 Implementar el óvalo con el video: `aspect-[3/4] w-full max-w-xs max-h-[70vh]` (o equivalente), `rounded-full overflow-hidden bg-inverse-surface`, `<video>` con `object-cover absolute inset-0 w-full h-full`.
- [x] 6.4 Implementar el anillo del óvalo con estado visual: borde dashed en reposo, `scanning-ring` (animación pulsante) mientras el motor está activo, borde success al completar.
- [x] 6.5 Implementar el spinner de carga del motor: overlay semi-transparente sobre el óvalo mientras `!motorListo && !motorError && !fallbackManual`.
- [x] 6.6 Implementar el indicador "CÁMARA EN VIVO" (badge rojo con punto pulsante) superpuesto al óvalo.
- [x] 6.7 Implementar la sección inferior: texto del paso actual (reto en curso, `text-title-xl` o equivalente), dots de progreso (● resuelto / ○ pendiente) + contador "N / total".
- [x] 6.8 Implementar la etiqueta contextual opcional: si `contextLabel` está definido, mostrarlo como texto pequeño sobre el óvalo o debajo del título.
- [x] 6.9 Implementar la UI de estado de error de cámara: mostrar mensaje con `Icon name="videocam_off"`, texto "Sin acceso a la cámara" e instrucción de habilitar permiso en el navegador.
- [x] 6.10 Implementar el banner de fallback manual: banner de advertencia tipo warning-container cuando `fallbackManual` es true.
- [x] 6.11 Implementar la grilla de botones de retos en fallback: igual que C-34, botones habilitados/deshabilitados por `hecho`, estilo success cuando completado.

## 7. Refactorizar Biometria.tsx para usar BiometricCapture

- [x] 7.1 Importar `BiometricCapture` en `Biometria.tsx` y el tipo `FaceLandmark` desde `VisionEngine`; importar `embeddingFromLandmarks` desde `MediaPipeVisionEngine`.
- [x] 7.2 Eliminar: los estados `desafios` y `resueltos`; la función `iniciar()`; la función `resolver(id)`; el bloque de reto con `desafios.map(...)` y botones manuales; el `useEffect` de cámara que asigna `streamRef`/`videoRef` (la cámara pasa a ser responsabilidad de `BiometricCapture`); `videoRef`, `streamRef`, `DESAFIOS`, `pickActiveChallenges`, `DesafioActivo` (si no se usan en otro lado).
- [x] 7.3 Implementar `handleComplete(landmarks: FaceLandmark[])`: calcula embedding con `embeddingFromLandmarks(landmarks)`, llama `verificar()` (adaptando la firma si es necesario para recibir el embedding).
- [x] 7.4 Implementar `handleCancel()`: vuelve a la fase `preparar`.
- [x] 7.5 En el render de fase `capturando`: reemplazar toda la sección de retos manuales por `<BiometricCapture onComplete={handleComplete} onCancel={handleCancel} contextLabel="Verificación de identidad" />`.
- [x] 7.6 Mantener el render de fases `preparar`, `verificando`, `verificado`, `reintento` sin cambios (incluyendo el Card, el óvalo interno en fase `preparar` puede simplificarse o eliminarse si BiometricCapture toma la cámara desde el inicio).
- [x] 7.7 Verificar que la navegación a `/sala-espera` tras `verificado` sigue funcionando.

## 8. Refactorizar EnrollmentBiometricStep.tsx para usar BiometricCapture

- [x] 8.1 Importar `BiometricCapture` en `EnrollmentBiometricStep.tsx`.
- [x] 8.2 Eliminar los siguientes elementos (que pasan a `BiometricCapture`): `startDetectionLoop`, `resolverRetoFromLoop`, `resolverRetoManual`, `activarFullscreen`, `salirFullscreen`, `engineRef`, `challengeCountsRef`, `lastLandmarksRef`, `rafHandleRef`, `procesarCapturaRef`, `desafiosRef`, `resueltosRef`, `faseRef`, `motorListo`, `motorError`, `fallbackManual`, `fullscreenFallback`, `camaraLista`, `isMobileOrTouch`, `containerRef`, `videoRef`, `canvasRef`, `streamRef`, y los imports relacionados (`loadEnrollmentEngine`, `disposeEnrollmentEngine`, `evaluateChallenge`, `framesMinForChallenge`, `embeddingFromLandmarks` como inline — moverlos a `handleComplete`).
- [x] 8.3 Implementar `handleComplete(landmarks: FaceLandmark[])` en `EnrollmentBiometricStep`: calcular embedding con `embeddingFromLandmarks(landmarks)`, capturar imagen del video si hay `videoRef` disponible (o simplificar sin imagen si `BiometricCapture` no expone el video), llamar `api.guardarReferenciaBiometrica({ imagen, embedding })`, `setFase('completado')`, `onCapturada(referencia)`.
- [x] 8.4 Simplificar el `useEffect` de cleanup de `EnrollmentBiometricStep`: ya no gestiona RAF ni motor (los gestiona `BiometricCapture`). Solo retener cleanup de stream si sigue siendo necesario.
- [x] 8.5 En el render de fase `capturando`: reemplazar toda la sección de `<Card>` con loop/retos/fallback por `<BiometricCapture onComplete={handleComplete} onCancel={cancelarCaptura} contextLabel="Captura de referencia biométrica" />`.
- [x] 8.6 Mantener el encabezado contextual (`esRenovacion`, vigencia, nota de referencia anterior) en la fase `instrucciones` fuera del overlay de `BiometricCapture`.
- [x] 8.7 Mantener la nota de privacidad Ley 25.326 visible en fases `instrucciones` y `completado` (fuera del overlay).
- [x] 8.8 Mantener las fases `instrucciones`, `procesando`, `completado` y `error` de `EnrollmentBiometricStep` sin cambios funcionales.

## 9. Actualizar CHANGES.md con C-36

- [x] 9.1 Agregar la entrada `C-36` en `CHANGES.md`: título `c-36-verificacion-biometrica-inmersiva`, estado `[ ]`, fase Refinamiento, scope (componente compartido `BiometricCapture`, refactor `Biometria.tsx` + `EnrollmentBiometricStep.tsx`, UI inmersiva), dependencias (C-34), governance (Tier 2 — frontend refactor + UX).
- [x] 9.2 Actualizar el contador total de changes en el encabezado de `CHANGES.md` a 36.

## 10. Validación

- [x] 10.1 Verificar con `openspec validate --strict` que los artefactos del change C-36 son válidos (0 errores).
- [x] 10.2 Revisar manualmente que `Biometria.tsx` en fase `capturando` ya no tiene botones con `onClick={() => resolver(d.id)}`.
- [x] 10.3 Revisar manualmente que `EnrollmentBiometricStep.tsx` ya no tiene `startDetectionLoop`, `engineRef`, ni `challengeCountsRef`.
- [x] 10.4 Revisar manualmente que `BiometricCapture.tsx` usa `await import('./RealMediaPipeVisionEngine')` (import dinámico, NO estático) para mantener @mediapipe/tasks-vision fuera del bundle inicial.
- [x] 10.5 Verificar que el tipo `FaceLandmark[]` fluye correctamente desde `BiometricCapture.onComplete` hasta `embeddingFromLandmarks` en ambas pantallas.
