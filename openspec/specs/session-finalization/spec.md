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
El cálculo del score final SHALL ser **idempotente y reintentable**; si la tarea de cierre falla, el score final SHALL poder recomputarse desde los eventos persistidos en la hypertable, sin pérdida.

#### Scenario: Reintento de la consolidación no duplica el score
- **WHEN** la tarea de consolidación se reintenta tras una falla
- **THEN** el score final resultante es el mismo, sin doble conteo, recomputado desde los eventos persistidos

