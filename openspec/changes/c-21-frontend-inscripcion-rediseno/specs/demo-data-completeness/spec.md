# Spec — demo-data-completeness

> Datos de demo enriquecidos y coherentes que dan panorama completo del producto en todas las pantallas (estudiante, proctor, revisor, admin, reportes, auditoría).

## ADDED Requirements

### Requirement: Todas las pantallas muestran contenido realista
El sistema SHALL proveer, desde la API mock, datos suficientes y coherentes para que cada pantalla de la demo muestre contenido representativo del producto (no placeholders vacíos), incluyendo exámenes, inscripciones, sesiones en vivo, cola de revisión, métricas de reportes y registros de auditoría.

#### Scenario: Pantalla de staff con datos completos
- **WHEN** un usuario de staff (proctor, revisor, admin) abre su pantalla
- **THEN** ve datos de demo realistas y completos que ilustran el caso de uso

#### Scenario: Reportes y auditoría con métricas
- **WHEN** se abren Reportes o Auditoría/Privacidad
- **THEN** se muestran métricas y registros de demo coherentes con el resto de los datos
