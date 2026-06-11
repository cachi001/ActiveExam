# biometric-capture-av-feedback Specification

## Purpose
TBD - created by archiving change c-65-fixes-captura-liveness-biometrica. Update Purpose after archive.
## Requirements
### Requirement: La captura emite un sonido de fallo además del de acierto

El catálogo de feedback auditivo (`sounds.ts`) SHALL incluir `playError()`, un tono discreto (≤ 250 ms, descendente) generado con WebAudio, que respeta `prefers-reduced-motion`, el cooldown por nombre y el flag `setSoundEnabled`, igual que los sonidos existentes.

El sistema SHALL disparar `playError()` en los fallos relevantes de la captura: timeout de baseline sin éxito, liveness pasivo fallido al cierre, cámara virtual detectada, o error de captura/cámara. El sonido de acierto (`playSuccess`) y de paso (`playStepCompleted`) se conservan.

#### Scenario: Falla la captura y suena el error
- **WHEN** la captura termina en un estado de fallo (p. ej. cámara virtual detectada o error de cámara)
- **THEN** se invoca `playError()` una vez

#### Scenario: Respeta el silencio del usuario
- **WHEN** `setSoundEnabled(false)` o `prefers-reduced-motion` está activo
- **THEN** `playError()` no emite sonido

#### Scenario: Acierto sigue sonando
- **WHEN** la captura se completa con éxito
- **THEN** suena `playSuccess()` (sin cambios respecto al comportamiento actual)

### Requirement: El anillo de progreso del óvalo se renderiza alineado con la guía

El anillo de progreso SHALL renderizarse con la misma orientación que el track de fondo y que el clip-path vertical (portrait) del video, sin transformaciones que intercambien sus ejes. El sistema NO SHALL aplicar `transform="rotate(-90 …)"` (ni rotaciones de 90°) al elemento `<ellipse>` de progreso, dado que rotar una elipse no circular intercambia sus ejes mayor/menor y la desalinea.

#### Scenario: Anillo coincide con el óvalo
- **WHEN** se renderiza el anillo de progreso sobre el óvalo de captura
- **THEN** el anillo de progreso y el track de fondo comparten orientación (vertical) y coinciden con el recorte del video

#### Scenario: Progreso se llena sin rotación de 90°
- **WHEN** el progreso avanza de 0 a 1
- **THEN** el trazo se llena a lo largo del mismo óvalo vertical, sin aparecer rotado/apaisado

