# Spec — evidence-audit-log

> Audit log **append-only** con hashes encadenados que registra cada operación sobre la evidencia (depósito, acceso, firma) de forma inmutable y verificable (RN-CC-07, `04` §Audit log).

## ADDED Requirements

### Requirement: Audit log append-only inmutable
El audit log de evidencia SHALL ser **append-only**: un trigger de base de datos SHALL rechazar toda operación UPDATE o DELETE sobre sus entradas.

#### Scenario: UPDATE/DELETE rechazado
- **WHEN** se intenta un UPDATE o DELETE sobre una entrada del audit log
- **THEN** el trigger de la base de datos lo rechaza y la entrada permanece inalterada

### Requirement: Encadenamiento de hash entre entradas
Cada entrada del audit log SHALL incluir el **hash de la entrada anterior** (`hash_entrada_anterior`), formando una cadena verificable cuya integridad se valida periódicamente.

#### Scenario: Cada entrada referencia el hash de la previa
- **WHEN** se escribe una nueva entrada en el audit log
- **THEN** la entrada incluye `hash_entrada_anterior` calculado sobre la entrada inmediatamente previa, encadenándolas

#### Scenario: Validación de integridad de la cadena
- **WHEN** se valida la integridad del audit log
- **THEN** recalcular la cadena de hashes detecta cualquier inserción, borrado o alteración fuera de orden

### Requirement: Registro de cada operación sobre la evidencia con propósito
El backend SHALL escribir una entrada en el audit log por cada operación relevante sobre la evidencia (depósito, firma, acceso/descarga), incluyendo `actor`, `timestamp`, `IP`, `user-agent`, `acción`, `evidencia_id` y `propósito` declarado cuando aplique.

#### Scenario: Depósito de evidencia auditado
- **WHEN** el backend deposita una evidencia en el bucket WORM
- **THEN** escribe una entrada de audit log con el actor (sistema/backend), la acción "depósito" y la referencia a la `evidencia_id`

#### Scenario: Acceso a evidencia auditado con propósito
- **WHEN** un actor autorizado solicita una URL de descarga de un clip
- **THEN** se registra una entrada de audit log con el actor, la acción "acceso", la `evidencia_id` y el propósito declarado
