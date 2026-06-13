# biometric-gesture-progress-resume Specification

## ADDED Requirements

### Requirement: El progreso del gesto se preserva al perder el gesto y reanuda sin reiniciar

El sistema SHALL acumular el progreso del gesto activo en términos de **tiempo efectivo de gesto cumplido** (un acumulador por reto), de modo que el progreso NO se derive exclusivamente del temporizador instantáneo de hold que se reinicia al perder el gesto.

Cuando el gesto se **pierde** (la condición deja de cumplirse), el relleno visual del gesto activo SHALL ocultarse, pero el progreso acumulado SHALL **preservarse** (no descartarse). Cuando el gesto se **reanuda** (la condición vuelve a cumplirse tras el gate de neutralidad), el relleno SHALL continuar **desde donde quedó**, sin reiniciarse a cero.

El reto SHALL confirmarse cuando el progreso acumulado alcance el umbral de tiempo configurado (`GESTURE_HOLD_MS`). Al confirmar el reto o al avanzar a otro reto, el acumulador de ese reto SHALL reiniciarse.

#### Scenario: El gesto se pierde y el progreso no vuelve a cero

- **WHEN** el alumno sostiene el gesto hasta el 60% del progreso y luego lo pierde un instante
- **THEN** el relleno visual del gesto activo se oculta
- **THEN** el progreso acumulado se conserva en ~60% (no se descarta)

#### Scenario: El gesto se reanuda y continúa desde donde quedó

- **WHEN** el alumno recupera el gesto correcto tras haberlo perdido al 60%
- **THEN** el relleno continúa desde ~60% hacia el 100% (no reinicia a 0)
- **THEN** el reto se confirma al completar el tiempo acumulado restante

#### Scenario: Al confirmar el reto el acumulador se reinicia

- **WHEN** el reto activo se confirma
- **THEN** el acumulador de progreso de ese reto se reinicia a cero para el siguiente reto
