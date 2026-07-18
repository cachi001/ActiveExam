## ADDED Requirements

### Requirement: Deadline efectivo calculado server-side

El sistema SHALL calcular el vencimiento de una rendición como `min(cierre_del_examen, creada_en + tiempo_limite_min)`, usando **exclusivamente la hora del servidor** (`datetime.now(timezone.utc)`). Cuando `tiempo_limite_min` es `null` (sin límite individual), el deadline efectivo SHALL ser el `cierre` del examen. El cliente SHALL NOT participar en el cálculo: la hora informada por el navegador nunca es entrada de esta decisión (regla dura de dominio #6).

#### Scenario: El límite individual vence antes que la ventana

- **WHEN** un alumno arranca a las 10:00 un examen con `tiempo_limite_min = 40` y ventana que cierra a las 12:00
- **THEN** el deadline efectivo de esa rendición es 10:40

#### Scenario: La ventana cierra antes que el límite individual

- **WHEN** un alumno arranca a las 11:50 un examen con `tiempo_limite_min = 40` y ventana que cierra a las 12:00
- **THEN** el deadline efectivo de esa rendición es 12:00, no 12:30

#### Scenario: Examen sin límite individual

- **WHEN** un alumno rinde un examen con `tiempo_limite_min = null` y ventana que cierra a las 12:00
- **THEN** el deadline efectivo de esa rendición es 12:00

#### Scenario: La hora del cliente no altera el deadline

- **WHEN** un cliente envía una petición declarando una hora local distinta de la del servidor
- **THEN** el deadline efectivo se calcula con la hora del servidor y la hora declarada por el cliente SHALL ser ignorada

### Requirement: El reloj de la rendición no se pausa

El deadline efectivo SHALL anclarse a `creada_en` de la sesión y SHALL NOT pausarse, reiniciarse ni extenderse por desconexión, recarga de página, cierre del navegador ni reanudación. El tiempo transcurrido mientras el alumno estuvo ausente SHALL contar como tiempo de examen.

#### Scenario: Volver dentro del plazo conserva el tiempo restante

- **WHEN** un alumno cierra el navegador en el minuto 10 de un examen de 40 y vuelve en el minuto 20
- **THEN** se reanuda la misma sesión con el mismo `creada_en` y le restan 20 minutos

#### Scenario: Cerrar el navegador no funciona como botón de pausa

- **WHEN** un alumno cierra el navegador en el minuto 10 de un examen de 40 y vuelve en el minuto 50
- **THEN** el deadline efectivo ya venció y la rendición no admite más respuestas

### Requirement: Margen de gracia invisible al cliente

El sistema SHALL aceptar mutaciones de la rendición hasta un margen de gracia configurable después del deadline efectivo, para absorber latencia de red y desfasaje de reloj. El margen SHALL NOT exponerse en ninguna respuesta de la API ni proyección de rendición, de modo que el cliente **no pueda derivarlo ni mostrarlo**: si el alumno percibiera la gracia, ésta pasaría a ser el límite real. La gracia SHALL tolerar latencia, NOT otorgar tiempo adicional de examen.

#### Scenario: Respuesta en vuelo dentro de la gracia se acepta

- **WHEN** el alumno envía una respuesta antes del deadline efectivo y ésta llega al servidor pocos segundos después del vencimiento, dentro del margen de gracia
- **THEN** el sistema acepta y persiste la respuesta

#### Scenario: Respuesta pasada la gracia se rechaza

- **WHEN** llega una respuesta después del deadline efectivo más el margen de gracia
- **THEN** el sistema la rechaza con `409 tiempo_agotado` y no la persiste

#### Scenario: El margen de gracia no viaja al cliente

- **WHEN** se inspecciona cualquier respuesta de la API relacionada con la rendición
- **THEN** ningún campo expone el margen de gracia ni un deadline que lo incluya
