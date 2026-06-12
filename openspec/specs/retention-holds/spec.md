# retention-holds Specification

## Purpose
TBD - created by archiving change c-19-retencion-holds. Update Purpose after archive.
## Requirements
### Requirement: Hold por caso disciplinario abierto
El sistema SHALL extender automáticamente la retención de los datos vinculados a un caso disciplinario abierto, impidiendo su eliminación mientras el hold esté activo.

#### Scenario: Datos bajo hold no se eliminan
- **WHEN** existe un caso disciplinario abierto vinculado a un dato que cumpliría su plazo de retención
- **THEN** el sistema extiende la retención y no elimina el dato

### Requirement: Liberación del hold al cerrar el caso
El sistema SHALL liberar el hold cuando el caso disciplinario se cierra, devolviendo los datos al régimen de retención normal.

#### Scenario: Hold liberado tras cerrar el caso
- **WHEN** un caso disciplinario que imponía un hold se cierra
- **THEN** el siguiente ciclo de retención aplica la política normal sobre los datos antes retenidos

#### Scenario: Reanudación de erasure diferida
- **WHEN** una solicitud de eliminación (DSR) había quedado diferida por este hold
- **THEN** al liberarse el hold, la eliminación puede reanudarse conforme al régimen de retención

