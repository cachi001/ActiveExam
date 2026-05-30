# Spec — event-persistence-timescale

> Persistencia del evento validado en la hypertable de TimescaleDB, con el `ts_backend` y los índices del modelo de datos (DD-05, `04_modelo_de_datos.md §Evento`).

## ADDED Requirements

### Requirement: Persistencia en hypertable de TimescaleDB
El backend SHALL persistir cada evento validado en la hypertable de eventos de TimescaleDB (particionada por día), conservando todos los campos del contrato incluido `ts_backend`.

#### Scenario: Evento validado se inserta en la hypertable
- **WHEN** un evento con firma válida pasa la validación
- **THEN** el backend lo inserta en la hypertable de eventos con su `ts_backend` completado

#### Scenario: Evento rechazado no llega a la hypertable
- **WHEN** un evento es rechazado por firma inválida o ausente
- **THEN** no se inserta ninguna fila correspondiente en la hypertable

### Requirement: Índices de consulta por sesión y por examen
La persistencia SHALL soportar consultas eficientes por `(session_id, ts)` y por `(exam_id, ts)` mediante los índices del modelo de datos, para habilitar el replay por `last_event_id` (C-14) y las lecturas del panel/scoring.

#### Scenario: Consulta de eventos posteriores a last_event_id
- **WHEN** se consultan los eventos de una sesión posteriores a un `last_event_id` dado
- **THEN** la consulta resuelve usando el índice `(session_id, ts)` y devuelve los eventos faltantes en orden
