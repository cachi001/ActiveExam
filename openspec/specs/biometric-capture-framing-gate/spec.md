# biometric-capture-framing-gate Specification

## Purpose
TBD - created by archiving change c-65-fixes-captura-liveness-biometrica. Update Purpose after archive.
## Requirements
### Requirement: Las advertencias de encuadre bloqueantes pausan la evaluación de retos

El sistema SHALL clasificar cada `FramingHint` como **bloqueante** o **informativo**. El óvalo es referencia DURA: TODO `FramingHint` no nulo SHALL ser bloqueante — `sin_rostro`, `multiples_rostros`, `poca_luz`, `mucha_luz`, `lejos`, `cerca` y `descentrado`. Estar fuera del óvalo (`descentrado`) SHALL detener la evaluación del reto igual que cualquier otra advertencia. Sólo `null` (encuadre correcto) SHALL ser no-bloqueante.

Mientras un hint bloqueante esté activo (tras pasar la histéresis de estabilidad existente), el loop RAF de `BiometricCapture.tsx` NO SHALL evaluar ni acumular progreso del reto activo: el acumulador de confirmación del reto SHALL mantenerse en su valor previo sin incrementarse. El sistema SHALL reanudar la evaluación recién cuando `framingHint` vuelve a `null`.

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

#### Scenario: Descentrado (fuera del óvalo) detiene la captura
- **WHEN** el único hint activo es `descentrado` (el rostro no está centrado en el óvalo)
- **THEN** la evaluación del reto activo no corre y se le pide al alumno centrarse
- **THEN** el reto reanuda recién cuando el rostro vuelve al centro del óvalo (`framingHint` pasa a `null`)

### Requirement: El gate de encuadre no interrumpe el liveness pasivo ni la detección de cámara virtual

El sistema SHALL seguir acumulando la ventana de liveness pasivo y ejecutando `detectVirtualCamera` en cada frame aun cuando un hint bloqueante esté activo. El gate de encuadre SHALL afectar únicamente la evaluación/acumulación del reto secuencial activo, no las señales pasivas.

#### Scenario: Liveness pasivo sigue corriendo bajo gate
- **WHEN** un hint bloqueante está activo y hay rostro detectado con landmarks
- **THEN** la ventana de liveness pasivo se sigue actualizando y `detectVirtualCamera` se sigue invocando

### Requirement: La captura de referencia exige pose frontal (mirar de frente)

El sistema SHALL exigir que la **cabeza** esté derecha / de frente para: (a) declarar el baseline neutral del cual se captura el frame de referencia que alimenta el embedding, y (b) avanzar cualquier reto que NO sea de giro. La frontalidad SHALL medirse por la **pose de la cabeza** (asimetría horizontal de la nariz respecto a las comisuras externas de los ojos en los landmarks de Face Mesh), NO por la mirada de los ojos (gaze/iris): el alumno mira la PANTALLA, no la cámara, por lo que exigir que el iris apunte a la lente sería antinatural. El umbral SHALL ser tolerante (sólo bloquea con la cabeza claramente girada). Cuando la cabeza no está de frente, el sistema SHALL emitir el hint bloqueante `no_frontal` ("Mirá de frente").

El sistema NO SHALL exigir frontalidad durante el reto `girar_cabeza` (ni otros retos cuyo id empiece con `girar`), porque ese reto pide explícitamente girar la cabeza. La exigencia de frontalidad SHALL suprimirse mientras ese reto esté activo.

#### Scenario: Cabeza girada al posicionarse no captura la referencia
- **WHEN** el encuadre estático está OK pero el rostro está girado (gaze fuera del umbral frontal) durante el baseline
- **THEN** el baseline no se declara y se muestra `no_frontal` ("Mirá de frente")
- **THEN** la referencia se captura recién cuando el rostro mira de frente

#### Scenario: El reto girar_cabeza no es bloqueado por la exigencia de frontalidad
- **WHEN** el reto activo es `girar_cabeza` y el alumno gira la cabeza
- **THEN** la exigencia de frontalidad se suprime y el reto se evalúa normalmente

