## ADDED Requirements

### Requirement: La finalización computa la nota solo sobre las respuestas en plazo

La finalización de una sesión SHALL calcular la nota exclusivamente sobre las respuestas persistidas dentro del plazo. Como el envío de respuestas fuera de plazo ya se rechaza (deadline enforcement), al finalizar NO existen respuestas tardías que puntuar: llegar tarde a finalizar NO SHALL otorgar ninguna ventaja. La finalización manual NO SHALL bloquearse por el vencimiento del deadline — es el acto de cierre ("lapiceras abajo"); el cierre de una sesión vencida sin intervención del alumno lo realiza la auto-finalización.

#### Scenario: Finalización dentro de plazo

- **WHEN** el alumno finaliza su sesión antes del deadline efectivo
- **THEN** la sesión se cierra y la nota se calcula sobre las respuestas persistidas

#### Scenario: Un intento tardío no agranda la nota

- **WHEN** un envío de respuestas posterior al deadline fue rechazado y luego el alumno finaliza la sesión
- **THEN** la nota se calcula únicamente sobre las respuestas persistidas en plazo

### Requirement: La finalización es idempotente

La finalización SHALL ser idempotente: finalizar una sesión ya finalizada SHALL NOT recalcular ni re-certificar la nota, de modo que re-finalizar un intento ya entregado no pueda alterar la nota.

#### Scenario: Doble finalización no recalcula

- **WHEN** se finaliza dos veces la misma sesión
- **THEN** la segunda finalización responde sin modificar `finalizada_en` ni recalcular la nota
