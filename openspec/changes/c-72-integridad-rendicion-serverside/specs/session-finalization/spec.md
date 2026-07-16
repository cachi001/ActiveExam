## ADDED Requirements

### Requirement: La finalización revalida el estado temporal de la rendición

La finalización de una sesión SHALL evaluar el deadline efectivo con hora del servidor y SHALL registrar si el cierre ocurrió dentro o fuera de plazo. Una finalización fuera de plazo SHALL NOT ampliar el conjunto de respuestas puntuables: la nota SHALL calcularse exclusivamente sobre las respuestas persistidas **antes** del vencimiento, de modo que llegar tarde a finalizar NO SHALL otorgar ninguna ventaja.

#### Scenario: Finalización dentro de plazo

- **WHEN** el alumno finaliza su sesión antes del deadline efectivo
- **THEN** la sesión se cierra y la nota se calcula sobre las respuestas persistidas

#### Scenario: Finalización tardía no otorga ventaja

- **WHEN** el alumno finaliza su sesión después del deadline efectivo
- **THEN** la sesión se cierra y la nota se calcula únicamente sobre las respuestas persistidas antes del vencimiento

#### Scenario: El cierre fuera de plazo queda asentado

- **WHEN** una sesión se finaliza después de su deadline efectivo
- **THEN** el sistema deja registro de que el cierre ocurrió fuera de plazo, disponible para el revisor humano

### Requirement: La finalización nunca certifica una nota de una rendición cerrada sin registro

El sistema SHALL NOT calcular y certificar la nota de una rendición cuya ventana ya cerró sin dejar constancia del hecho. La certificación de una nota SHALL ser un acto trazable: el estado temporal en que se produjo el cierre SHALL formar parte del registro de la sesión.

#### Scenario: Nota certificada con la ventana cerrada queda trazada

- **WHEN** se finaliza una sesión cuya ventana de examen ya cerró y se calcula su nota
- **THEN** el registro de la sesión refleja que el cierre ocurrió con la ventana cerrada
