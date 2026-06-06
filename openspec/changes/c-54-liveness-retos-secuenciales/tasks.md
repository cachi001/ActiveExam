## 1. Actualizar catálogo de retos en liveness.ts

- [x] 1.1 Agregar la constante `SEQUENTIAL_CHALLENGES = ['parpadear', 'girar_cabeza', 'sonreír'] as const` y el tipo `SequentialChallenge` en `liveness.ts`
- [x] 1.2 Agregar el tipo `ChallengeState` para la máquina de estados: `'idle' | 'baseline' | 'challenge' | 'cooldown' | 'done'`
- [x] 1.3 Agregar el tipo `BaselineMetrics` con campos `blinkOpenness`, `smileWidth`, `gazeX` (promedios del baseline neutral)
- [x] 1.4 Agregar el tipo `TurnDirection = 'izquierda' | 'derecha'` para la dirección aleatoria del reto de giro
- [x] 1.5 Marcar `ACTIVE_CHALLENGES` como `@deprecated` con jsdoc (no eliminar aún — puede usarse en otros contextos); `pickActiveChallenges` igual
- [x] 1.6 Verificar que ningún otro módulo fuera del flujo de enrollment/verificación biométrica importe `ACTIVE_CHALLENGES` directamente; actualizar imports si es necesario

## 2. Agregar evaluación relativa al baseline en enrollmentChallengeDetector.ts

- [x] 2.1 Exportar las nuevas constantes de evaluación relativa: `BLINK_RELATIVE_FACTOR = 0.45`, `SMILE_RELATIVE_FACTOR = 1.25`, `GAZE_TURN_THRESHOLD_ADJUSTED = 0.22`
- [x] 2.2 Exportar los nuevos mínimos de frames: `FRAMES_MIN_BLINK_SEQ = 3`, `FRAMES_MIN_TURN_SEQ = 4`, `FRAMES_MIN_SMILE_SEQ = 4`
- [x] 2.3 Crear la función `evaluateChallengeRelative(challenge, landmarks, gaze, baseline, turnDirection?)` que evalúa con delta relativo al baseline: parpadear usa `openness < baseline.blinkOpenness * BLINK_RELATIVE_FACTOR`; girar_cabeza usa la condición DIRECCIONAL según `turnDirection` (`'izquierda'` → `gaze.x > +GAZE_TURN_THRESHOLD_ADJUSTED`; `'derecha'` → `gaze.x < -GAZE_TURN_THRESHOLD_ADJUSTED`, respetando la convención de espejo de `enrollmentChallengeDetector.ts`); sonreír usa `smileWidth > baseline.smileWidth * SMILE_RELATIVE_FACTOR`
- [x] 2.4 Crear la función `framesMinForChallengeSeq(challenge)` que retorna los nuevos `FRAMES_MIN_*_SEQ`
- [x] 2.5 Mantener `evaluateChallenge()` y `framesMinForChallenge()` existentes como `@deprecated` (compatibilidad hacia atrás)

## 3. Implementar máquina de estados de baseline en BiometricCapture.tsx

- [x] 3.1 Agregar ref `challengeIndexRef = useRef(0)` (índice del reto activo en la secuencia barajada)
- [x] 3.2 Agregar ref `baselineRef = useRef<BaselineMetrics | null>(null)` (métricas del baseline neutral)
- [x] 3.3 Agregar ref `baselineAccumulatorRef = useRef<Array<{ blinkOpenness, smileWidth, gazeX }>>([])` (buffer de frames para el baseline; se empieza a acumular desde el frame 10 de cara detectada)
- [x] 3.4 Agregar ref `baselineFrameCountRef = useRef(0)` (contador de frames totales de detección, para el timeout y para esperar al frame 10+)
- [x] 3.5 Agregar ref `bestReferenceFrameRef = useRef<HTMLCanvasElement | null>(null)` (frame capturado durante el baseline para el embedding)
- [x] 3.6 Agregar ref `cooldownActiveRef = useRef(false)` y `cooldownTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)`
- [x] 3.7 Barajar `SEQUENTIAL_CHALLENGES` con Fisher-Yates usando `Math.random()` al montar el componente y guardar el resultado en `desafiosBarajadosRef` (ref o estado estable)
- [x] 3.8 Elegir aleatoriamente `turnDirection: TurnDirection` (`'izquierda'` o `'derecha'`) con `Math.random() < 0.5` al montar el componente y guardarlo en `turnDirectionRef`

## 4. Implementar la fase baseline en el loop RAF de BiometricCapture.tsx

- [x] 4.1 En el loop RAF, antes de evaluar retos, verificar si `baselineRef.current === null` (fase baseline activa)
- [x] 4.2 En fase baseline: incrementar `baselineFrameCountRef.current` en cada frame con cara detectada; solo acumular métricas en `baselineAccumulatorRef` a partir del frame 10 (cuando `baselineFrameCountRef.current >= 10`) para evitar subexposición inicial de cámara (OQ-3)
- [x] 4.3 En cada frame acumulado (frame 10+): registrar blinkOpenness = |lm[159].y − lm[145].y|, smileWidth = |lm[291].x − lm[61].x|, gazeX = gaze.x
- [x] 4.4 Verificar estabilidad: si `baselineAccumulatorRef.current.length >= 12` y la varianza de nariz (landmark 1) es < 0.002, declarar baseline estable; calcular promedios; validar que `baselineSmileWidth <= 0.14`
- [x] 4.5 Si `baselineSmileWidth > 0.14`, resetear el acumulador y actualizar la UI con mensaje "Relajá la expresión y mirá al frente"
- [x] 4.6 Si el baseline es válido: capturar el frame actual del `<video>` en un canvas y guardarlo en `bestReferenceFrameRef.current` (este es el frame de calidad para el embedding)
- [x] 4.7 Si `baselineFrameCountRef.current >= 60` y aún no hay baseline, usar los últimos 10 frames disponibles como fallback y declarar baseline (sin el check de smileWidth)

## 5. Implementar la evaluación secuencial en el loop RAF de BiometricCapture.tsx

- [x] 5.1 Eliminar el loop `for (const id of currentDesafios)` que evaluaba todos los retos en paralelo
- [x] 5.2 Si `baselineRef.current === null` o `cooldownActiveRef.current === true`, saltar la evaluación de retos en el frame
- [x] 5.3 Obtener el reto activo: `const retoActivo = desafiosBarajadosRef.current[challengeIndexRef.current]`; si `challengeIndexRef.current >= desafiosBarajadosRef.current.length`, no evaluar (ya están todos resueltos)
- [x] 5.4 Evaluar el reto activo con `evaluateChallengeRelative(retoActivo, landmarks, gaze, baselineRef.current, turnDirectionRef.current)` — pasar `turnDirectionRef.current` para que el giro sea DIRECCIONAL
- [x] 5.5 Si cumple: incrementar `challengeCountsRef.current.get(retoActivo)`; si llega a `framesMinForChallengeSeq(retoActivo)`, activar el cooldown
- [x] 5.6 Si no cumple: resetear el acumulador del reto activo a 0
- [x] 5.7 Si `face_count === 0`: resetear el acumulador del reto activo (mantener comportamiento existente)

## 6. Implementar el cooldown y la transición entre retos en BiometricCapture.tsx

- [x] 6.1 Crear la función `activarCooldown(retoResueltoId)`: marcar `cooldownActiveRef.current = true`, invocar `resolverRetoFromLoop(retoResueltoId)`, programar `setTimeout` de **350 ms** que llama a `avanzarAlSiguienteReto()`
- [x] 6.2 Crear la función `avanzarAlSiguienteReto()`: incrementar `challengeIndexRef.current`; limpiar `cooldownActiveRef.current = false`; si `challengeIndexRef.current >= desafiosBarajadosRef.current.length`, el loop RAF no evaluará más retos (la fase exito ya fue activada por `resolverRetoFromLoop`)
- [x] 6.3 En el cleanup del `useEffect` de inicialización, limpiar `cooldownTimerRef.current` si está activo (prevenir memory leaks)

## 7. Actualizar procesarCompletado en BiometricCapture.tsx para usar el frame del baseline

- [x] 7.1 Reemplazar el canvas capturado del `<video>` al momento de `procesarCompletado()` por `bestReferenceFrameRef.current` cuando está disponible
- [x] 7.2 Si `bestReferenceFrameRef.current` es null (baseline no capturado, modo fallback manual), mantener la captura del frame actual como fallback
- [x] 7.3 Asegurarse de que el frame entregado al caller vía `onComplete` sea `bestReferenceFrameRef.current ?? frameActual`

## 8. Agregar estado de cooldown e instrucción direccional a la UI en CaptureProgress.tsx

- [x] 8.1 Agregar la prop `cooldownActivo: boolean` a `CaptureProgressProps`
- [x] 8.2 Agregar la prop `retoRecienResueltoLabel: string | null` (label del reto que acaba de completarse, para mostrar en cooldown)
- [x] 8.3 Agregar la prop `turnDirection: TurnDirection | null` para mostrar "a la DERECHA" / "a la IZQUIERDA" cuando el reto activo es `girar_cabeza`
- [x] 8.4 Cuando `cooldownActivo === true` y `!enExito`, mostrar un estado de confirmación: ícono de check verde + "Paso N completado" + el `retoRecienResueltoLabel`
- [x] 8.5 Cuando el reto activo es `girar_cabeza` y `cooldownActivo === false`, mostrar la instrucción DIRECCIONAL: "Girá la cabeza a la DERECHA" o "Girá la cabeza a la IZQUIERDA" (según `turnDirection`), con indicador visual de dirección (flecha o texto destacado)
- [x] 8.6 Cuando `cooldownActivo === false` y el reto no es `girar_cabeza`, mostrar el reto activo actual normalmente

## 9. Propagar cooldownActivo, turnDirection y retoRecienResuelto desde BiometricCapture.tsx hacia CaptureOverlay y CaptureProgress

- [x] 9.1 Agregar estado de React `cooldownActivo` sincronizado con `cooldownActiveRef` (usar `setFase` o un estado dedicado)
- [x] 9.2 Agregar estado `retoRecienResuelto: SequentialChallenge | null` que se actualiza cuando se resuelve un reto y se limpia al salir del cooldown
- [x] 9.3 Exponer `turnDirectionRef.current` como estado o valor estable para pasarlo a la UI (puede ser un estado inicializado al montar: `const [turnDirection] = useState<TurnDirection>(...)`)
- [x] 9.4 Pasar `cooldownActivo`, `retoRecienResueltoLabel` y `turnDirection` a `CaptureOverlay`
- [x] 9.5 Actualizar la interfaz de `CaptureOverlayProps` para incluir las nuevas props (`cooldownActivo`, `retoRecienResueltoLabel`, `turnDirection`)
- [x] 9.6 Pasar las props desde `CaptureOverlay` a `CaptureProgress`

## 10. Verificar compatibilidad de callers y resolver OQ-1

- [x] 10.1 Verificar en `api.ts` / mock que `retosResueltos` sin `acercarse` no rompe ninguna validación del mock backend; si la lista de retos esperados está hardcodeada, actualizarla
- [x] 10.2 Verificar que `EnrollmentBiometricStep.tsx` no necesita cambios (la firma de `onComplete` no cambia; solo cambia el `frame` entregado)
- [x] 10.3 Verificar que `Biometria.tsx` (verificación durante el examen, si usa `BiometricCapture` directamente) funciona con el nuevo catálogo
- [x] 10.4 Verificar que el tipo `ActiveChallenge` en `liveness.ts` sigue siendo compatible con todo el código que lo importa (agregar `girar_cabeza` si no existe; puede ser un alias de `girar_izquierda | girar_derecha` o un valor nuevo)

## 11. Tests unitarios del nuevo motor

- [x] 11.1 Test de `evaluateChallengeRelative()` para `parpadear`: caso positivo (ojo bien cerrado sobre baseline), caso negativo (variación natural), caso sin baseline (debe retornar false)
- [x] 11.2 Test de `evaluateChallengeRelative()` para `sonreír`: caso positivo (sonrisa genuina), caso negativo (cara en reposo), caso baseline con smileWidth alto (alumno sonreía al baseline)
- [x] 11.3 Test de `evaluateChallengeRelative()` para `girar_cabeza` DIRECCIONAL:
  - Con `turnDirection = 'izquierda'`: `gaze.x = +0.25` → true (giro correcto); `gaze.x = -0.25` → false (giro en dirección equivocada); `gaze.x = 0` → false (al frente)
  - Con `turnDirection = 'derecha'`: `gaze.x = -0.25` → true (giro correcto); `gaze.x = +0.25` → false (giro en dirección equivocada)
- [x] 11.4 Test de `framesMinForChallengeSeq()`: verificar que retorna **3** para parpadear y **4** para giro y sonrisa
- [x] 11.5 Test de validación del baseline: baseline con smileWidth > 0.14 se invalida; acumulación no comienza antes del frame 10; baseline con < 12 frames (frames 10+) no se declara; timeout a los 60 frames usa fallback
- [x] 11.6 Test de aleatorización: verificar que la función de barajado Fisher-Yates produce las 6 permutaciones posibles de `SEQUENTIAL_CHALLENGES` (test probabilístico con N=1000 iteraciones: cada permutación debe aparecer con frecuencia ~1/6)
