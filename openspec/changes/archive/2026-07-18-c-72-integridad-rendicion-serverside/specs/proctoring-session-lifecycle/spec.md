## ADDED Requirements

### Requirement: La reanudación de una sesión emite su evento server-side

Cuando el sistema reanuda una sesión activa existente en vez de crear una nueva, SHALL emitir el evento de reanudación correspondiente **desde el servidor**, en el momento del resume. El evento SHALL NOT depender de que el cliente lo reporte: el servidor sabe con certeza que reanudó, y un cliente modificado SHALL ser incapaz de suprimir, falsear o desactivar el registro (regla dura de dominio #6 — el sensor que reportaría la conducta es el mismo que la ejecuta).

#### Scenario: Reanudar emite el evento sin intervención del cliente

- **WHEN** un alumno vuelve a abrir un examen y el sistema reanuda su sesión activa existente
- **THEN** el sistema emite el evento de reanudación server-side, asociado a esa sesión

#### Scenario: Un cliente modificado no puede suprimir el registro

- **WHEN** un cliente manipulado reanuda una rendición sin reportar ningún evento de recarga
- **THEN** el evento de reanudación queda registrado igualmente, porque lo emite el servidor

#### Scenario: Crear una sesión nueva no emite evento de reanudación

- **WHEN** un alumno arranca una rendición y no existe sesión activa previa para ese examen
- **THEN** se crea una sesión nueva y NO se emite evento de reanudación

### Requirement: El evento de reanudación registra la duración de la ausencia

El evento de reanudación SHALL registrar la **duración de la ausencia** medida server-side, y esa duración SHALL determinar el tipo emitido según el catálogo (reanudación rápida vs. tardía). La duración SHALL quedar disponible para el revisor humano, porque es la señal que distingue una falla de infraestructura de una consulta externa: la reanudación por sí sola NO SHALL interpretarse como conducta indebida.

#### Scenario: Ausencia breve emite reanudación rápida

- **WHEN** una sesión se reanuda tras una ausencia breve
- **THEN** el evento emitido es el de reanudación rápida, con la duración registrada

#### Scenario: Ausencia prolongada emite reanudación tardía

- **WHEN** una sesión se reanuda tras una ausencia prolongada
- **THEN** el evento emitido es el de reanudación tardía, con la duración registrada

#### Scenario: La duración es visible para el revisor

- **WHEN** un revisor humano abre el contexto de una sesión que registró reanudaciones
- **THEN** puede ver cuánto duró cada ausencia, no solo que hubo una reanudación

### Requirement: La reanudación no altera el deadline de la rendición

La reanudación de una sesión SHALL conservar `creada_en` inmutable y SHALL NOT extender, pausar ni reiniciar el deadline efectivo. Reanudar SHALL restaurar el estado de la rendición (respuestas ya persistidas y tiempo restante real), NOT otorgar tiempo adicional.

#### Scenario: Reanudar conserva el ancla temporal

- **WHEN** el sistema reanuda una sesión activa
- **THEN** devuelve la misma sesión con el mismo `creada_en` y el mismo deadline efectivo que antes de la interrupción

#### Scenario: Reanudar restaura las respuestas ya guardadas

- **WHEN** un alumno reanuda una rendición dentro del plazo
- **THEN** las respuestas que había persistido siguen disponibles y puede continuar con el tiempo restante real
