# tabla-accion-sticky Specification

## Purpose
TBD - created by archiving change c-76-panel-supervision-en-vivo. Update Purpose after archive.
## Requirements
### Requirement: Columna de acciones fija en scroll horizontal
La columna de **acciones** (última columna de la tabla) SHALL permanecer **fija (sticky)** al hacer scroll horizontal, de modo que el botón de acción esté siempre visible sin necesidad de desplazar la tabla en X. Es un requisito puramente presentacional; no cambia la lógica ni la autoridad de las acciones.

#### Scenario: Acción visible durante scroll horizontal
- **WHEN** el usuario hace scroll horizontal en una tabla ancha con columna de acciones
- **THEN** la columna de acciones permanece fija y visible en el borde de la tabla

#### Scenario: Sin scroll horizontal el layout no se rompe
- **WHEN** la tabla entra completa en el viewport (no requiere scroll horizontal)
- **THEN** la columna de acciones se muestra en su posición normal sin artefactos visuales

