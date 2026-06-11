# biometric-liveness-active Specification

## Purpose
TBD - created by archiving change c-49-cablear-codigo-fantasma-proctoring. Update Purpose after archive.
## Requirements
### Requirement: BiometricCapture calcula liveness pasivo real con ventana deslizante
El sistema SHALL mantener un acumulador de ventana circular de N=15 frames en `BiometricCapture.tsx`. En cada frame del loop RAF, el sistema SHALL calcular:
- `blinkVariance`: varianza de apertura vertical del ojo izquierdo (landmarks[159].y − landmarks[145].y) y ojo derecho (landmarks[386].y − landmarks[374].y) entre los frames de la ventana.
- `motionVariance`: varianza de la posición (x, y) del centroide de nariz (landmark 1) entre frames.
- `depthRange`: max(z) − min(z) de todos los valores z de la ventana.

El sistema SHALL invocar `derivePassiveSignals({ blinkVariance, motionVariance, depthRange })` y `passivePassed(signals)` para determinar `passiveOk`.

#### Scenario: Liveness pasivo pasa con rostro vivo
- **WHEN** el alumno parpadea normalmente y realiza micro-movimientos en los últimos 15 frames
- **THEN** `blinkVariance > 0.01`, `motionVariance > 0.0005` y `depthRange > 0.02`
- **THEN** `passivePassed()` retorna `true` y `passiveOk` es `true`

#### Scenario: Liveness pasivo falla con imagen estática
- **WHEN** el feed de cámara muestra una imagen estática (foto o video en loop)
- **THEN** las varianzas calculadas son ≈ 0 y `depthRange ≈ 0`
- **THEN** `passivePassed()` retorna `false` y `passiveOk` es `false`

#### Scenario: Timeout conservador — no bloquear alumno legítimo
- **WHEN** `passiveOk` es `false` por más de 90 frames consecutivos (≈3 segundos de RAF)
- **THEN** el sistema NO bloquea el flujo ni interrumpe los retos activos
- **THEN** el sistema propaga `passiveOk: false` al callback `onComplete` para revisión humana (L2.5)

#### Scenario: Sin landmarks — ventana vacía
- **WHEN** `face_count === 0` y no hay landmarks disponibles en el frame
- **THEN** el acumulador no agrega métricas al frame actual
- **THEN** `passiveOk` se mantiene en el último valor calculado o `false` si la ventana está vacía

### Requirement: BiometricCapture detecta cámara virtual en el loop RAF
El sistema SHALL invocar `detectVirtualCamera({ interFramePixelVariance, frameRateJitter, faceCountStability })` en cada frame del loop. `interFramePixelVariance` se calcula sobre un canvas de 16×12 píxeles (diferencia cuadrática media entre frames consecutivos, escala de grises). `frameRateJitter` se deriva de la desviación estándar de `performance.now()` entre frames en la ventana. `faceCountStability` es la proporción de frames con `face_count === 1` en la ventana.

#### Scenario: Cámara virtual detectada
- **WHEN** `interFramePixelVariance < 1e-6` y `faceCountStability >= 0.999`
- **THEN** `detectVirtualCamera()` retorna `true`
- **THEN** `virtualCameraDetected` se propaga como `true` al callback `onComplete`

#### Scenario: Cámara física normal
- **WHEN** hay varianza de píxeles normal entre frames y jitter natural de la cámara
- **THEN** `detectVirtualCamera()` retorna `false`
- **THEN** `virtualCameraDetected` es `false` en el callback `onComplete`

### Requirement: BiometricCapture propaga retos resueltos reales al callback
El sistema SHALL propagar `resueltosRef.current` al invocar `onComplete`, reemplazando el valor hardcodeado `[]` en `Biometria.tsx`. Los retos resueltos son los `ActiveChallenge[]` que el alumno completó durante la sesión.

#### Scenario: Retos resueltos propagados correctamente
- **WHEN** el alumno completa los retos `['parpadear', 'girar_izquierda']` y el componente invoca `onComplete`
- **THEN** el tercer parámetro de `onComplete` contiene `['parpadear', 'girar_izquierda']`
- **THEN** `Biometria.tsx` envía `retos_resueltos: ['parpadear', 'girar_izquierda']` al backend

#### Scenario: Fallback manual — retos marcados manualmente propagados
- **WHEN** el motor falla y el alumno completa los retos en modo manual
- **THEN** `resueltosRef.current` contiene los retos marcados manualmente
- **THEN** `passiveOk` es `false` (no hay métricas de landmarks en modo fallback)

### Requirement: Biometria.tsx usa liveness_ok real (no hardcodeado)
El sistema SHALL eliminar el `liveness_ok: true` hardcodeado en `Biometria.tsx`. El valor SHALL derivarse del resultado `passiveOk` recibido en el callback `onComplete`. El sistema SHALL enviar a `api.enviarBiometriaProctoring` el valor real de `passiveOk`.

#### Scenario: liveness_ok refleja resultado real
- **WHEN** `BiometricCapture` completa y retorna `passiveOk: false`
- **THEN** `api.enviarBiometriaProctoring` recibe `liveness_ok: false`
- **THEN** el backend recibe la señal honesta para revisión humana

#### Scenario: liveness_ok true solo con pasivo real aprobado
- **WHEN** `BiometricCapture` completa y retorna `passiveOk: true`
- **THEN** `api.enviarBiometriaProctoring` recibe `liveness_ok: true`

### Requirement: La evaluación secuencial de retos queda subordinada al gate de encuadre y al umbral por tiempo

La evaluación del reto activo en el loop RAF de `BiometricCapture.tsx` SHALL estar subordinada, en este orden, a: (1) el cooldown entre pasos, (2) el gate de encuadre (no evaluar bajo hint bloqueante — ver `biometric-capture-framing-gate`), y (3) el criterio de confirmación por tiempo sostenido (ver `biometric-gesture-hold-timing`). El sistema NO SHALL confirmar un reto por conteo de frames como condición primaria.

Esta subordinación SHALL preservar intactos el liveness pasivo (ventana N=15) y la detección de cámara virtual descriptos en esta capability: ambos siguen ejecutándose por frame con independencia del gate.

#### Scenario: Orden de subordinación respetado
- **WHEN** hay un hint bloqueante activo o un cooldown en curso
- **THEN** la evaluación del reto activo no corre
- **THEN** la confirmación del reto, cuando corre, requiere sostenimiento por tiempo (no conteo de frames)

#### Scenario: Señales pasivas no se ven afectadas
- **WHEN** la evaluación de retos está pausada por el gate de encuadre
- **THEN** el liveness pasivo y `detectVirtualCamera` siguen actualizándose por frame

