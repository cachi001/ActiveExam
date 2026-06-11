# db-migrations-baseline Specification

## Purpose
TBD - created by archiving change c-04-foundation-setup. Update Purpose after archive.
## Requirements
### Requirement: Migración 001 habilita TimescaleDB sobre esquema vacío
La migración 001 SHALL habilitar la extensión TimescaleDB y dejar el esquema **sin tablas de dominio**, de modo que C-05 pueda crear la hypertable de eventos sobre la extensión ya presente.

#### Scenario: 001 deja la extensión presente y el esquema vacío
- **WHEN** se aplica la migración 001 sobre una base limpia
- **THEN** la extensión TimescaleDB queda habilitada y no existe ninguna tabla de dominio (las entidades llegan en C-05)

#### Scenario: 001 es reversible
- **WHEN** se revierte la migración 001
- **THEN** la extensión se remueve sin pérdida, dado que el esquema no contiene tablas de dominio

### Requirement: Convención de migraciones destructivas en dos pasos
Alembic SHALL adoptar la convención de **migraciones destructivas en dos pasos** (expand/contract) desde el inicio, para que todo cambio destructivo futuro se ejecute sin downtime ni pérdida de datos.

#### Scenario: Cambio destructivo dividido en expand y contract
- **WHEN** una migración futura requiere eliminar o renombrar una columna/tabla
- **THEN** se ejecuta en dos pasos (primero expandir/compatibilizar, luego contraer/eliminar) conforme a la convención establecida en este change

