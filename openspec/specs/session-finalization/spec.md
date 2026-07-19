# session-finalization Specification

## Purpose
TBD - created by archiving change c-13-scoring-incremental. Update Purpose after archive.
## Requirements
### Requirement: Cierre de sesión dispara consolidación asíncrona
`POST /sessions/{id}/finish` SHALL disparar una **tarea asíncrona** que consolida las métricas de la sesión y calcula el **score final**, sin bloquear la respuesta al estudiante (RN-SC-04).

#### Scenario: Cierre devuelve sin esperar el cálculo
- **WHEN** el estudiante finaliza la sesión vía `POST /sessions/{id}/finish`
- **THEN** la sesión se marca como finalizada y una tarea asíncrona consolida métricas y calcula el score final en background

### Requirement: Liberación de la clave de sesión al cierre
Al cerrar la sesión, el sistema SHALL **liberar la clave de sesión rotativa**, de modo que no se acepten más eventos firmados de esa sesión.

#### Scenario: Clave liberada tras el cierre
- **WHEN** la sesión se cierra
- **THEN** la clave de sesión rotativa se libera y los eventos firmados con ella ya no son aceptados

### Requirement: Score final consolidado idempotente y recomputable
El cálculo del score final SHALL ser **idempotente y reintentable**; si la tarea de cierre falla, el score final SHALL poder recomputarse desde los eventos persistidos, sin pérdida. El cálculo SHALL ponderar los eventos usando los **pesos vivos** leídos desde la configuración persistida (`evento_score_config` + `configuracion_sistema`), NO mapas hardcodeados; el fallback por defecto SHALL usarse solo como red de seguridad de degradación. La consolidación SHALL registrar la `version` de configuración usada, de modo que un cambio posterior de configuración no altere el score de sesiones ya finalizadas.

#### Scenario: Reintento de la consolidación no duplica el score
- **WHEN** la tarea de consolidación se reintenta tras una falla
- **THEN** el score final resultante es el mismo, sin doble conteo, recomputado desde los eventos persistidos

#### Scenario: La consolidación usa los pesos vivos de la config
- **WHEN** se finaliza una sesión tras una edición de pesos en la configuración
- **THEN** el score final SHALL calcularse con los pesos persistidos vigentes (no con `_PESO_SEVERIDAD_DEFAULT`)

#### Scenario: La versión de config queda registrada en la consolidación
- **WHEN** se consolida una sesión
- **THEN** el resultado SHALL registrar la `version` de configuración utilizada en el cálculo

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

