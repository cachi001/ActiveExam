# Spec — embedding-egress-deletion

> Eliminación del embedding biométrico al egreso (modelo de datos §Embedding).

## ADDED Requirements

### Requirement: Eliminación del embedding al egreso del estudiante
El sistema SHALL eliminar el embedding biométrico cifrado del estudiante cuando este egresa.

#### Scenario: Embedding eliminado al egreso
- **WHEN** un estudiante egresa
- **THEN** el sistema elimina su embedding biométrico cifrado

### Requirement: Eliminación del embedding verificable
El sistema SHALL registrar la eliminación del embedding en el audit log, sin reexponer el vector.

#### Scenario: Eliminación del embedding registrada
- **WHEN** se elimina el embedding por egreso
- **THEN** queda una entrada en el audit log que documenta la eliminación sin contener el vector biométrico
