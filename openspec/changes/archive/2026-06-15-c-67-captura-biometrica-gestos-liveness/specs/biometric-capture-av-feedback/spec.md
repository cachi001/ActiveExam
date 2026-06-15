# biometric-capture-av-feedback Specification

## MODIFIED Requirements

### Requirement: La captura emite sonidos de acierto, fallo y progreso de gesto

El catálogo de feedback auditivo (`sounds.ts`) SHALL incluir `playError()`, un tono discreto (≤ 250 ms, descendente) generado con WebAudio, que respeta `prefers-reduced-motion`, el cooldown por nombre y el flag `setSoundEnabled`, igual que los sonidos existentes.

El sistema SHALL disparar `playError()` en los fallos relevantes de la captura: timeout de baseline sin éxito, liveness pasivo fallido al cierre, cámara virtual detectada, o error de captura/cámara. El sonido de acierto (`playSuccess`) y de paso (`playStepCompleted`) se conservan.

El catálogo SHALL incluir además dos señales de progreso de gesto: una señal mientras el gesto progresa correctamente (p. ej. `playGestureProgress()`, disparada por cruce de fracción de progreso, no por frame) y una señal distinta cuando el progreso se detiene por pérdida del gesto (p. ej. `playGestureLost()`). Ambas SHALL respetar `prefers-reduced-motion`, `setSoundEnabled(false)` y el cooldown por nombre, y SHALL ser distinguibles entre sí y de `playError`/`playHint`. (El detalle de comportamiento de estas señales se especifica en la capability `biometric-gesture-audio-cues`.)

#### Scenario: Falla la captura y suena el error
- **WHEN** la captura termina en un estado de fallo (p. ej. cámara virtual detectada o error de cámara)
- **THEN** se invoca `playError()` una vez

#### Scenario: Respeta el silencio del usuario
- **WHEN** `setSoundEnabled(false)` o `prefers-reduced-motion` está activo
- **THEN** ni `playError()` ni las señales de progreso/pérdida de gesto emiten sonido

#### Scenario: Acierto sigue sonando
- **WHEN** la captura se completa con éxito
- **THEN** suena `playSuccess()` (sin cambios respecto al comportamiento actual)

#### Scenario: Progreso de gesto suena de forma discreta
- **WHEN** el alumno sostiene el gesto correcto y el relleno cruza fracciones de progreso
- **THEN** se emite la señal de progreso de gesto sin estallar en bucle (cooldown por nombre)

### Requirement: El anillo de progreso del óvalo se renderiza alineado y en el borde exterior, con trazo fino

El anillo de progreso SHALL renderizarse con la misma orientación que el track de fondo y que el clip-path vertical (portrait) del video, sin transformaciones que intercambien sus ejes. El sistema NO SHALL aplicar `transform="rotate(-90 …)"` (ni rotaciones de 90°) al elemento `<ellipse>` de progreso, dado que rotar una elipse no circular intercambia sus ejes mayor/menor y la desalinea.

El anillo de progreso SHALL ubicarse en el **borde exterior** del óvalo, fuera del recorte del video, de modo que no se superponga a la imagen del rostro. El trazo SHALL ser fino y minimalista (grosor reducido respecto del trazo grueso previo), tanto en el track de fondo como en el trazo de progreso. (El detalle de ubicación y relleno verde progresivo se especifica en la capability `biometric-gesture-progress-ring`.)

#### Scenario: Anillo coincide con el óvalo
- **WHEN** se renderiza el anillo de progreso sobre el óvalo de captura
- **THEN** el anillo de progreso y el track de fondo comparten orientación (vertical) y coinciden con el recorte del video

#### Scenario: Progreso se llena sin rotación de 90°
- **WHEN** el progreso avanza de 0 a 1
- **THEN** el trazo se llena a lo largo del mismo óvalo vertical, sin aparecer rotado/apaisado

#### Scenario: El anillo queda en el borde exterior y es fino
- **WHEN** se renderiza el anillo de progreso
- **THEN** el trazo se dibuja en el contorno externo del óvalo (no sobre la imagen del rostro)
- **THEN** el grosor del trazo es fino/minimalista (menor que el grueso previo)
