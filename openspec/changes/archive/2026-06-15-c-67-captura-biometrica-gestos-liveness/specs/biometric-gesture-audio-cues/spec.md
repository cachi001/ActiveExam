# biometric-gesture-audio-cues Specification

## ADDED Requirements

### Requirement: Señal auditiva mientras el gesto progresa correctamente

El catálogo de feedback auditivo (`sounds.ts`) SHALL incluir una señal de progreso de gesto (p. ej. `playGestureProgress()`), un tono breve generado con WebAudio que se emite mientras el gesto del reto activo progresa correctamente. La señal SHALL dispararse por **cruce de fracción de progreso** (no por cada frame), de modo que no sature ni estalle en bucle.

La señal SHALL respetar `prefers-reduced-motion`, el flag `setSoundEnabled(false)` y el cooldown por nombre, igual que el resto del catálogo.

#### Scenario: Suena mientras el relleno avanza

- **WHEN** el alumno sostiene el gesto correcto y el relleno cruza fracciones de progreso
- **THEN** se emite la señal de progreso de forma discreta (no por frame)

#### Scenario: Respeta el silencio del usuario

- **WHEN** `setSoundEnabled(false)` o `prefers-reduced-motion` está activo
- **THEN** la señal de progreso no emite sonido

### Requirement: Señal auditiva cuando el progreso se detiene (gesto perdido)

El catálogo SHALL incluir una señal de pérdida de gesto (p. ej. `playGestureLost()`), un tono distinto del de progreso, del de fallo terminal (`playError`) y del de encuadre (`playHint`), que se emite cuando el gesto se pierde (la condición deja de cumplirse con progreso acumulado mayor que cero) y el relleno se oculta.

La señal SHALL respetar `prefers-reduced-motion`, `setSoundEnabled(false)` y el cooldown por nombre.

#### Scenario: Suena cuando se pierde el gesto y se oculta el relleno

- **WHEN** el alumno estaba progresando y pierde el gesto correcto
- **THEN** se emite la señal de pérdida una vez y el relleno del gesto activo se oculta

#### Scenario: No suena la pérdida si no había progreso

- **WHEN** el gesto nunca empezó a progresar (progreso acumulado en cero) y la condición no se cumple
- **THEN** no se emite la señal de pérdida
