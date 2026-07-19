# session-auto-finalization Specification

## Purpose
TBD - created by archiving change c-72-integridad-rendicion-serverside. Update Purpose after archive.
## Requirements
### Requirement: La sesión vencida se finaliza automáticamente

El sistema SHALL finalizar automáticamente toda sesión activa (`finalizada_en IS NULL`) cuyo deadline efectivo haya vencido, sin requerir acción del alumno. La finalización automática SHALL ser indistinguible de la manual en cuanto al cálculo de nota y al write-back: una sesión abandonada NO SHALL quedar activa indefinidamente.

#### Scenario: Sesión abandonada se finaliza al vencer

- **WHEN** un alumno cierra el navegador en el minuto 20 de un examen de 40 y no vuelve nunca
- **THEN** al vencer el deadline efectivo la sesión queda finalizada con `finalizada_en` seteado

#### Scenario: Sesión vencida detectada al reintentar acceso

- **WHEN** un alumno vuelve a la plataforma después de que su deadline efectivo venció
- **THEN** el sistema finaliza esa sesión y NO SHALL permitirle continuar respondiendo

### Requirement: La sesión auto-finalizada se puntúa con lo respondido

El sistema SHALL calcular la nota de una sesión auto-finalizada sobre las respuestas que el alumno alcanzó a persistir antes del vencimiento. Una sesión auto-finalizada SHALL NOT puntuarse 0 por el solo hecho de no haber sido entregada explícitamente: el alumno SHALL conservar el resultado del trabajo que efectivamente realizó.

#### Scenario: Corte de conexión no funde el examen

- **WHEN** un alumno responde 14 de 20 preguntas y pierde la conexión definitivamente
- **THEN** la sesión se finaliza automáticamente y la nota se calcula sobre las 14 respuestas persistidas

#### Scenario: Sesión sin ninguna respuesta

- **WHEN** una sesión se auto-finaliza sin ninguna respuesta persistida
- **THEN** la nota se calcula sobre cero respuestas y la sesión queda finalizada de forma consistente

#### Scenario: Write-back normal tras auto-finalización

- **WHEN** una sesión se auto-finaliza y tiene nota calculada
- **THEN** el write-back de la nota sigue el mismo camino que una finalización manual, incluido su gate de revisión

### Requirement: La auto-finalización es idempotente

La finalización automática SHALL ser idempotente: ejecutarla más de una vez sobre la misma sesión SHALL NOT mutar `finalizada_en` ya seteado, NOT recalcular una nota ya consolidada, y NOT duplicar el write-back. Una carrera entre la finalización automática y la manual SHALL resolverse en un único cierre.

#### Scenario: Barrido repetido no muta la sesión

- **WHEN** el mecanismo de auto-finalización procesa dos veces la misma sesión vencida
- **THEN** `finalizada_en` conserva el valor del primer cierre y no se duplica el write-back

#### Scenario: Carrera entre cierre automático y manual

- **WHEN** el alumno finaliza manualmente en el mismo instante en que el mecanismo automático cierra su sesión vencida
- **THEN** la sesión queda finalizada una sola vez, con una única nota consolidada

