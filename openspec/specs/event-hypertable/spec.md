# event-hypertable Specification

## Purpose
TBD - created by archiving change c-05-core-models. Update Purpose after archive.
## Requirements
### Requirement: Evento como hypertable TimescaleDB con índices del modelo
El Evento SHALL ser una hypertable TimescaleDB particionada por día (chunks), con el esquema de `04` §Evento (`session_id`, `exam_id` denormalizado, `tipo`, `severidad`, `timestamp_cliente`, `timestamp_backend`, `payload` JSON, `firma` HMAC, `schema_version`) y los índices `(session_id, timestamp)` y `(exam_id, timestamp)`.

#### Scenario: Hypertable creada con sus índices
- **WHEN** se aplica la migración 002 (sobre la extensión TimescaleDB habilitada por C-04)
- **THEN** el Evento es una hypertable particionada por día con los índices `(session_id, timestamp)` y `(exam_id, timestamp)` presentes

#### Scenario: Esquema del Evento completo
- **WHEN** se inspecciona la tabla de Evento
- **THEN** contiene las columnas `session_id`, `exam_id`, `tipo`, `severidad`, `timestamp_cliente`, `timestamp_backend`, `payload`, `firma` y `schema_version` (`04` §Evento)

### Requirement: Compresión escalonada y continuous aggregates base
El Evento SHALL aplicar una política de compresión (chunks <7 días sin comprimir, >7 días comprimidos) y SHALL exponer los continuous aggregates base de `04` §Evento (eventos por sesión por minuto, score por sesión, sesiones activas por examen, distribución por tipo).

#### Scenario: Política de compresión 7d/>7d activa
- **WHEN** se revisa la configuración de la hypertable tras la 002
- **THEN** existe una política que mantiene los chunks de los últimos 7 días sin comprimir y comprime los de más de 7 días (`04` §Evento)

#### Scenario: Continuous aggregates base materializados
- **WHEN** se consultan los agregados de paneles
- **THEN** están disponibles los continuous aggregates base (eventos/sesión/min, score/sesión, sesiones activas/examen, distribución por tipo) para lectura sin escanear el raw (CQRS-lite, `08`)

