# Spec — dsr-auditability

> Trazabilidad de las operaciones DSR en el audit log append-only. US-013 CA-2.

## ADDED Requirements

### Requirement: Trazabilidad de toda operación DSR en el audit log
El sistema SHALL registrar toda operación DSR (acceso, rectificación, eliminación —incluida la diferida— y portabilidad) en el audit log append-only, con actor=titular, acción, propósito y timestamp, encadenado por hash.

#### Scenario: Operación DSR deja rastro encadenado
- **WHEN** se procesa cualquier operación DSR
- **THEN** se generan entradas en el audit log append-only encadenadas por hash con el actor titular y la acción correspondiente

### Requirement: La trazabilidad no reexpone datos eliminados
El audit log SHALL registrar que la operación ocurrió y su resultado (ejecutada o diferida) sin contener los datos personales que fueron eliminados o anonimizados.

#### Scenario: Auditoría sin reexponer PII
- **WHEN** se inspecciona el audit log de una eliminación
- **THEN** la entrada demuestra que la eliminación ocurrió y cuándo, sin contener los datos personales borrados

#### Scenario: Operación verificable en auditoría
- **WHEN** un auditor revisa el audit log y el residual de una eliminación
- **THEN** puede demostrar que la operación se ejecutó en plazo y de forma trazable
