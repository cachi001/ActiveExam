## MODIFIED Requirements

### Requirement: BiometricCapture evalúa retos activos en secuencia estricta con orden aleatorio, no en paralelo
El sistema SHALL evaluar los retos activos uno a la vez en **orden aleatorio** (barajado por Fisher-Yates con `Math.random()` al montar el componente), implementado como una máquina de estados con `challengeIndexRef`. En cada frame del loop RAF, solo el reto en `desafiosBarajados[challengeIndexRef.current]` SHALL evaluarse usando `evaluateChallengeRelative()` con el baseline neutral capturado y, para `girar_cabeza`, con la `turnDirection` elegida al azar. El loop `for (const id of currentDesafios)` paralelo SHALL ser eliminado. El reto `acercarse` SHALL ser removido del catálogo. El catálogo SHALL usar `SEQUENTIAL_CHALLENGES` de `liveness.ts` como base (antes de barajar).

#### Scenario: Solo un reto activo en cada frame
- **WHEN** `challengeIndexRef.current === 0` (cualquier reto activo, e.g. `sonreír`) y el alumno parpadea en el mismo frame
- **THEN** el sistema no avanza el reto `parpadear` (no está activo en esta posición)
- **THEN** solo se evalúa y acumula el frame para `sonreír`

#### Scenario: La secuencia sigue el orden barajado aleatorio
- **WHEN** el sistema barajó `[girar_cabeza, sonreír, parpadear]` al montar
- **THEN** tras el baseline, el primer reto activo es `girar_cabeza` con su `turnDirection`
- **WHEN** el alumno completa `girar_cabeza`
- **THEN** tras el cooldown de **350 ms**, `challengeIndexRef.current` avanza a 1 (`sonreír`)
- **WHEN** el alumno completa `sonreír`
- **THEN** tras el cooldown, avanza a 2 (`parpadear`)
- **WHEN** el alumno completa `parpadear`
- **THEN** el sistema transita a fase `exito`

#### Scenario: BiometricCapture pasa bestReferenceFrame al onComplete
- **WHEN** el baseline se captura con éxito y el alumno completa los 3 retos
- **THEN** `procesarCompletado()` entrega `bestReferenceFrameRef.current` al caller (no el último frame del video)
- **THEN** el caller (`EnrollmentBiometricStep`) puede computar `computeFaceDescriptor()` sobre un frame de cara frontal y neutral

#### Scenario: Modo fallback manual no se altera por este change
- **WHEN** el motor de visión falla y `fallbackManual` es `true`
- **THEN** el flujo de fallback manual sigue funcionando con botones por reto
- **THEN** los botones reflejan `SEQUENTIAL_CHALLENGES` (sin imponer orden específico en fallback)

#### Scenario: La instrucción de giro muestra la dirección concreta
- **WHEN** el reto activo es `girar_cabeza` con `turnDirection = 'izquierda'`
- **THEN** la UI muestra "Girá la cabeza a la IZQUIERDA" con indicador visual de dirección
- **WHEN** el reto activo es `girar_cabeza` con `turnDirection = 'derecha'`
- **THEN** la UI muestra "Girá la cabeza a la DERECHA" con indicador visual de dirección

## REMOVED Requirements

### Requirement: BiometricCapture evalúa TODOS los retos pendientes en paralelo en cada frame
**Reason**: La evaluación paralela era la causa raíz del bug "primer reto se autocompleta". Con umbrales absolutos permisivos, el primer reto de la lista que la cara en reposo satisfacía ganaba automáticamente. Reemplazado por evaluación secuencial estricta (ver Requirement modificado arriba).
**Migration**: Eliminar el `for (const id of currentDesafios) { if (currentResueltos.includes(id)) continue; ... }` en `BiometricCapture.tsx`. Reemplazar por acceso directo a `desafios[challengeIndexRef.current]`.

### Requirement: Los retos activos de enrollment incluyen acercarse
**Reason**: `acercarse` genera falsos positivos frecuentes (el umbral absoluto de bbox.width > 0.48 varía según la distancia inicial del alumno a la cámara y el hardware). No es un reto de liveness estándar en proctoring ni en banca. Su eliminación reduce la tasa de falsos positivos sin degradar la seguridad (los retos `parpadear`, `girar_cabeza` y `sonreír` son suficientes para el nivel L2.5).
**Migration**: Reemplazar `ACTIVE_CHALLENGES` con `SEQUENTIAL_CHALLENGES = ['parpadear', 'girar_cabeza', 'sonreír']` en `liveness.ts`. Actualizar toda referencia a `ACTIVE_CHALLENGES` en el flujo de enrollment. El catálogo del backend puede mantener `acercarse` para compatibilidad; el frontend simplemente no lo enviará en `retosResueltos`.

### Requirement: Los umbrales de retos son valores absolutos globales
**Reason**: Los umbrales absolutos (`SMILE_WIDTH_THRESHOLD=0.10`, `BLINK_CLOSE_THRESHOLD=0.018`, `GAZE_TURN_THRESHOLD=0.18`) no contemplan la variabilidad entre usuarios, iluminación y hardware. `SMILE_WIDTH_THRESHOLD=0.10` es satisfecho por la cara en reposo de muchos usuarios. Reemplazado por evaluación con delta relativo al baseline neutral del propio alumno.
**Migration**: Eliminar `SMILE_WIDTH_THRESHOLD` y `BLINK_CLOSE_THRESHOLD` como umbrales de evaluación directa. Reemplazar `evaluateChallenge()` por `evaluateChallengeRelative()` que recibe el baseline y, para `girar_cabeza`, la `turnDirection`. Los factores relativos (`BLINK_RELATIVE_FACTOR=0.45`, `SMILE_RELATIVE_FACTOR=1.25`) y el umbral de giro ajustado (`GAZE_TURN_THRESHOLD_ADJUSTED=0.22`) son las nuevas constantes de referencia. Los mínimos de frames quedan en `FRAMES_MIN_BLINK_SEQ=3`, `FRAMES_MIN_TURN_SEQ=4`, `FRAMES_MIN_SMILE_SEQ=4`.
