## ADDED Requirements

### Requirement: Las advertencias de encuadre bloqueantes pausan la evaluación de retos

El sistema SHALL clasificar cada `FramingHint` como **bloqueante** o **informativo**. Los hints bloqueantes SHALL ser, como mínimo: `sin_rostro`, `multiples_rostros`, `poca_luz`, `mucha_luz`, `lejos`, `cerca`. El hint `descentrado` SHALL ser informativo (no bloqueante).

Mientras un hint bloqueante esté activo (tras pasar la histéresis de estabilidad existente), el loop RAF de `BiometricCapture.tsx` NO SHALL evaluar ni acumular progreso del reto activo: el acumulador de confirmación del reto SHALL mantenerse en su valor previo sin incrementarse. El sistema SHALL reanudar la evaluación recién cuando `framingHint` vuelve a `null` (o a un hint informativo).

El gate de encuadre SHALL aplicarse con el mismo patrón de corte temprano que el `cooldownActiveRef` existente, y SHALL ser independiente de él.

#### Scenario: Poca luz no permite avanzar el reto
- **WHEN** el hint bloqueante `poca_luz` está activo y el alumno realiza el gesto del reto
- **THEN** el acumulador de confirmación del reto no se incrementa
- **THEN** el reto no se marca como completado mientras `poca_luz` siga activo

#### Scenario: Dos rostros en cuadro detienen la captura
- **WHEN** el hint `multiples_rostros` está activo
- **THEN** la evaluación del reto activo no corre, sin importar el movimiento del alumno

#### Scenario: Reanudación al normalizar el encuadre
- **WHEN** un hint bloqueante estaba activo y el encuadre se normaliza (`framingHint` pasa a `null`)
- **THEN** la evaluación del reto se reanuda desde el acumulador en cero (requiere el gate de neutralidad antes de contar positivos)

#### Scenario: Hint informativo no bloquea
- **WHEN** el único hint activo es `descentrado`
- **THEN** la evaluación del reto activo continúa normalmente

### Requirement: El gate de encuadre no interrumpe el liveness pasivo ni la detección de cámara virtual

El sistema SHALL seguir acumulando la ventana de liveness pasivo y ejecutando `detectVirtualCamera` en cada frame aun cuando un hint bloqueante esté activo. El gate de encuadre SHALL afectar únicamente la evaluación/acumulación del reto secuencial activo, no las señales pasivas.

#### Scenario: Liveness pasivo sigue corriendo bajo gate
- **WHEN** un hint bloqueante está activo y hay rostro detectado con landmarks
- **THEN** la ventana de liveness pasivo se sigue actualizando y `detectVirtualCamera` se sigue invocando
