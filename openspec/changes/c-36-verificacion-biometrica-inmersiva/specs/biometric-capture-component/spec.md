## ADDED Requirements

### Requirement: El componente BiometricCapture encapsula la captura biométrica inmersiva
El sistema SHALL proveer el componente `BiometricCapture` (`frontend/src/ui/BiometricCapture.tsx`) que encapsule: acceso a cámara (getUserMedia), loop RAF de detección real con el motor MediaPipe (vía `loadEnrollmentEngine`/`disposeEnrollmentEngine`), evaluación de retos (`evaluateChallenge`, `framesMinForChallenge`), selección aleatoria de retos (`pickActiveChallenges`), UI inmersiva (overlay `fixed inset-0`) y fallback manual. El componente SHALL recibir las props `onComplete(landmarks: FaceLandmark[])`, `onCancel()`, `contextLabel?: string`, `challengeCount?: number` y `challenges?: ActiveChallenge[]`.

#### Scenario: Retos aleatorios si no se pasan explícitamente
- **WHEN** `BiometricCapture` se monta sin la prop `challenges`
- **THEN** llama `pickActiveChallenges(challengeCount ?? 2)` para seleccionar los retos activos

#### Scenario: Retos explícitos si se pasan como prop
- **WHEN** `BiometricCapture` se monta con la prop `challenges` como array no vacío
- **THEN** usa esos retos directamente, sin llamar `pickActiveChallenges`

#### Scenario: El componente inicia la cámara al montar
- **WHEN** `BiometricCapture` se monta
- **THEN** llama `getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } })`
- **THEN** asigna el stream al elemento `<video>` interno

#### Scenario: El motor se carga lazy al montar
- **WHEN** `BiometricCapture` se monta
- **THEN** llama `loadEnrollmentEngine()` una vez
- **THEN** mientras el motor carga, muestra un spinner sobre el óvalo

#### Scenario: El loop RAF detecta retos en tiempo real
- **WHEN** el motor está listo y la fase es activa (capturando)
- **THEN** por cada frame, llama `evaluateChallenge(id, landmarks, gaze, bbox)` para cada reto pendiente
- **THEN** acumula frames consecutivos por reto en un `Map<ActiveChallenge, number>`
- **THEN** cuando el acumulador de un reto supera `framesMinForChallenge(id)`, marca ese reto como resuelto

#### Scenario: onComplete se llama al resolver todos los retos
- **WHEN** todos los retos han sido resueltos por el loop de detección
- **THEN** el componente llama `onComplete(lastLandmarks)` con los landmarks del último frame detectado
- **THEN** cancela el loop RAF
- **THEN** llama `disposeEnrollmentEngine()`

#### Scenario: onCancel se llama al presionar el botón cancelar
- **WHEN** el usuario presiona el botón cancelar del overlay
- **THEN** el componente llama `onCancel()`
- **THEN** cancela el loop RAF y llama `disposeEnrollmentEngine()`
- **THEN** detiene el stream de cámara

#### Scenario: Cleanup al desmontar
- **WHEN** el componente se desmonta (useEffect cleanup)
- **THEN** cancela el loop RAF si está activo
- **THEN** llama `disposeEnrollmentEngine()`
- **THEN** detiene todos los tracks del stream de cámara

### Requirement: La UI del componente es inmersiva con overlay a pantalla completa
El sistema SHALL renderizar el overlay del componente `BiometricCapture` con clase `fixed inset-0 z-50` con fondo sólido oscuro. El óvalo con la cámara SHALL dominar el centro (aspect `3/4`, `max-h-[70vh]`). El paso actual (texto del reto pendiente) SHALL mostrarse debajo del óvalo con tipografía grande (`text-title-xl` o equivalente). El progreso de retos (dots + "N / total") SHALL mostrarse debajo del paso actual. El botón cancelar SHALL ser discreto (top-right, opacidad reducida).

#### Scenario: Overlay cubre toda la pantalla en desktop
- **WHEN** `BiometricCapture` se renderiza en un viewport de escritorio (≥ 768 px)
- **THEN** el overlay con `fixed inset-0 z-50` cubre visualmente toda la ventana del navegador
- **THEN** no hay card, borde ni padding exterior visible

#### Scenario: Overlay cubre toda la pantalla en móvil
- **WHEN** `BiometricCapture` se renderiza en un viewport móvil (< 768 px)
- **THEN** el overlay con `fixed inset-0 z-50` cubre visualmente toda la pantalla del dispositivo

#### Scenario: requestFullscreen se intenta al activar el overlay
- **WHEN** el componente activa el overlay (inicio de captura)
- **THEN** intenta `containerRef.current.requestFullscreen()` como best-effort
- **THEN** si `requestFullscreen` rechaza o no está disponible, NO lanza error — el overlay CSS ya garantiza la cobertura

#### Scenario: El óvalo es el elemento visual dominante
- **WHEN** el overlay está activo y la cámara tiene stream
- **THEN** el óvalo con el video ocupa la mayor parte del área visual del overlay
- **THEN** el texto del paso actual es visible debajo del óvalo con fuente prominente

#### Scenario: El paso actual muestra el texto del reto pendiente
- **WHEN** hay al menos un reto no resuelto
- **THEN** el texto del paso actual muestra el label del reto en curso (ej. "Parpadeá", "Mirá a la izquierda")
- **THEN** el texto cambia al siguiente reto cuando el anterior se resuelve

#### Scenario: El progreso de retos muestra N / total
- **WHEN** el overlay está activo
- **THEN** se muestran indicadores (dots o contador) del tipo "retos resueltos / total"
- **THEN** los dots resueltos cambian a color success

### Requirement: BiometricCapture soporta fallback manual cuando el motor no puede cargar
El sistema SHALL detectar cuando `loadEnrollmentEngine()` rechaza (WebGL ausente u otro error) y SHALL activar el modo fallback manual donde los retos se resuelven con botones clicables. SHALL mostrar un banner de advertencia indicando que el modo de detección automática no está disponible.

#### Scenario: Fallback activo cuando loadEnrollmentEngine rechaza
- **WHEN** `loadEnrollmentEngine()` rechaza con cualquier error
- **THEN** `BiometricCapture` entra en modo fallback manual
- **THEN** muestra un banner "Motor de visión no disponible — modo de prueba manual"
- **THEN** los retos se muestran como botones clicables

#### Scenario: Resolver reto manualmente en fallback
- **WHEN** el usuario hace clic en un reto en modo fallback
- **THEN** ese reto se marca como resuelto
- **THEN** cuando todos los retos son resueltos manualmente, se llama `onComplete` con los últimos landmarks disponibles (puede ser array vacío)

### Requirement: BiometricCapture maneja el error de cámara no disponible
El sistema SHALL manejar el caso donde `getUserMedia` rechaza y SHALL mostrar un estado de error con mensaje claro, sin activar el loop RAF ni cargar el motor.

#### Scenario: Error de cámara al montar
- **WHEN** `getUserMedia` rechaza (permiso denegado u otro error)
- **THEN** el componente muestra el mensaje "Sin acceso a la cámara" con instrucción de habilitar permiso
- **THEN** el loop RAF no se inicia
- **THEN** no se carga el motor
