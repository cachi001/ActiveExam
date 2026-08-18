## ADDED Requirements

### Requirement: Etiqueta clara de la acción de subir nota
La acción de subir/publicar la nota SHALL presentarse con una **etiqueta clara** para el usuario, en lugar del texto ambiguo "sincronizar con Moodle". La autoridad para ejecutarla NO cambia: la conserva quien tiene `gestionar_notas` (tutor, admin de exámenes, coordinador, admin de sistema).

#### Scenario: Botón con etiqueta comprensible
- **WHEN** un usuario con `gestionar_notas` ve la tabla de notas
- **THEN** el botón de la acción indica claramente que sube/publica la nota (no dice "sincronizar con Moodle")

### Requirement: Subida de nota individual por fila
El sistema SHALL permitir subir la nota de **un** alumno de forma individual desde su fila, sin necesidad de operar sobre todo el conjunto.

#### Scenario: Subir nota de un solo alumno
- **WHEN** un usuario con `gestionar_notas` acciona subir nota en la fila de un alumno
- **THEN** se publica la nota de ese alumno únicamente

### Requirement: Selección de filas y subida en lote
La tabla de notas SHALL ofrecer un **checkbox** por fila (y selección múltiple) para subir en **lote** las notas de las filas seleccionadas mediante una acción "subir seleccionadas".

#### Scenario: Subida en lote de filas seleccionadas
- **WHEN** un usuario con `gestionar_notas` marca varias filas y acciona "subir seleccionadas"
- **THEN** se publican las notas de todas las filas seleccionadas

#### Scenario: Ninguna fila seleccionada
- **WHEN** el usuario acciona la subida en lote sin filas seleccionadas
- **THEN** la acción no publica ninguna nota y se indica que no hay selección
