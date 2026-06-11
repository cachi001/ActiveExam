# Spec — append-only-audit-log

> Capacidad de **audit log inmutable**: trigger que rechaza UPDATE/DELETE + hash encadenado (`hash_prev`). Base de la cadena de custodia (DD-07, `04` §Audit log). Su Done es: la base rechaza mutaciones y la cadena de hash es validable.

## ADDED Requirements

### Requirement: Audit log rechaza UPDATE y DELETE a nivel de motor
El audit log SHALL llevar un trigger que **rechaza** las operaciones `UPDATE` y `DELETE` (abortando con excepción), permitiendo únicamente `INSERT`, de modo que la inmutabilidad no dependa de la capa de aplicación (DD-07).

#### Scenario: INSERT permitido
- **WHEN** se inserta una entrada en el audit log
- **THEN** la inserción es aceptada

#### Scenario: UPDATE rechazado por el trigger
- **WHEN** se intenta hacer `UPDATE` sobre una fila del audit log (incluso por fuera de la aplicación)
- **THEN** el trigger aborta la operación con excepción y la fila no cambia

#### Scenario: DELETE rechazado por el trigger
- **WHEN** se intenta hacer `DELETE` sobre una fila del audit log
- **THEN** el trigger aborta la operación con excepción y la fila persiste

### Requirement: Encadenamiento de hash por entrada (hash_prev)
Cada entrada del audit log SHALL incluir `hash_prev` igual al hash de la entrada anterior, formando una cadena validable a diario que detecta inserción o borrado fuera de banda (`04` §Audit log).

#### Scenario: Cadena de hash consistente extremo a extremo
- **WHEN** se insertan N entradas consecutivas y se recorre la cadena
- **THEN** el `hash_prev` de cada entrada coincide con el hash de la anterior, y la verificación de la cadena completa pasa

#### Scenario: Ruptura de cadena detectable
- **WHEN** una entrada presenta un `hash_prev` que no corresponde a la anterior
- **THEN** la validación diaria de la cadena lo detecta como inconsistencia
