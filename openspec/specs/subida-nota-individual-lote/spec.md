# subida-nota-individual-lote Specification

## Purpose
TBD - created by archiving change c-76-panel-supervision-en-vivo. Update Purpose after archive.
## Requirements
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

### Requirement: Las políticas de intentos se resuelven por tiempo real
Cuando un alumno tiene más de un intento sobre el mismo examen y la política de intentos configurada es "último intento" o "primer intento", el sistema SHALL elegir la fila según el instante real de creación de la sesión (`creada_en`), NO según el identificador de sesión. Los identificadores de sesión son UUID aleatorios y su orden no guarda relación con el tiempo, de modo que ordenar por ellos elige una fila arbitraria.

El desempate entre dos sesiones con el mismo instante de creación SHALL ser determinístico (por identificador de sesión), para que dos ejecuciones sobre los mismos datos produzcan el mismo resultado.

#### Scenario: "Último intento" elige el más reciente
- **GIVEN** un alumno con dos sesiones del mismo examen creadas en instantes distintos
- **WHEN** se sincroniza con la política "último intento"
- **THEN** se publica la nota de la sesión creada más recientemente

#### Scenario: "Primer intento" elige el más antiguo
- **GIVEN** un alumno con dos sesiones del mismo examen creadas en instantes distintos
- **WHEN** se sincroniza con la política "primer intento"
- **THEN** se publica la nota de la sesión creada primero

#### Scenario: El resultado no depende del identificador de sesión
- **GIVEN** dos sesiones del mismo alumno donde el identificador de la más antigua ordena después que el de la más reciente
- **WHEN** se sincroniza con la política "último intento"
- **THEN** se publica igualmente la nota de la sesión más reciente por tiempo

#### Scenario: Desempate determinístico
- **GIVEN** dos sesiones del mismo alumno con idéntico instante de creación
- **WHEN** se sincroniza dos veces con la misma política
- **THEN** ambas ejecuciones eligen la misma fila

#### Scenario: La política "más alta" no cambia
- **GIVEN** un alumno con varios intentos de notas distintas
- **WHEN** se sincroniza con la política "nota más alta"
- **THEN** se publica la nota más alta, sin intervención de ningún criterio temporal

#### Scenario: La política manual no deduplica
- **WHEN** se sincroniza con la política manual
- **THEN** se publican todas las filas sincronizables seleccionadas, sin deduplicar por alumno

