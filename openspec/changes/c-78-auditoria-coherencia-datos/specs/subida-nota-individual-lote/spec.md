## ADDED Requirements

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
