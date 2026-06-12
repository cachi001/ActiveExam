# retention-policy-engine Specification

## Purpose
TBD - created by archiving change c-19-retencion-holds. Update Purpose after archive.
## Requirements
### Requirement: Aplicación automática de políticas de retención
El sistema SHALL aplicar automáticamente, sin intervención manual, las políticas de retención configuradas por tipo de dato (clips, embeddings, eventos, audit log, casos).

#### Scenario: Política aplicada automáticamente
- **WHEN** un dato supera el plazo de retención configurado para su tipo y no está bajo hold
- **THEN** el sistema aplica la política configurada sin acción manual

#### Scenario: Plazos configurables por tipo
- **WHEN** el DPO ajusta el plazo de retención de un tipo de dato
- **THEN** el motor aplica el nuevo plazo en los ciclos siguientes sin cambios de código

### Requirement: Respeto del Object Lock WORM
El motor de retención NO SHALL eliminar binarios bajo Object Lock (modo Compliance) antes de que expire su retención.

#### Scenario: Binario bajo Object Lock no se borra prematuramente
- **WHEN** un clip está bajo Object Lock con retención vigente
- **THEN** el motor no lo elimina hasta que expire el Object Lock

### Requirement: Operaciones de retención verificables
El sistema SHALL registrar cada aplicación de política de retención en el audit log append-only, sin reexponer datos personales eliminados.

#### Scenario: Aplicación de política registrada
- **WHEN** el motor aplica una política de retención
- **THEN** queda una entrada en el audit log que indica qué política, qué tipo de dato, cuándo y el resultado

