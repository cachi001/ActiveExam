## ADDED Requirements

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
