# Spec — event-fanout-backplane

> Fan-out del evento persistido a los paneles suscriptos vía el **backplane ganador de C-03** (`LISTEN/NOTIFY` o Redis Pub/Sub, sin asumir cuál), bajo el SLO de tiempo real p99 < 500 ms y cero pérdida de eventos confirmados (DD-16, `14`, RN-CC-08).

## ADDED Requirements

### Requirement: Fan-out a paneles vía el backplane ganador de C-03
El backend SHALL propagar cada evento persistido a los paneles suscriptos a través del backplane decidido por C-03, sin acoplar la implementación a una opción concreta: el adaptador de backplane SHALL ser sustituible por el ganador (`LISTEN/NOTIFY` o Redis Pub/Sub) sin reescribir la lógica de ingesta.

#### Scenario: Evento persistido se propaga a los paneles suscriptos
- **WHEN** un evento validado se persiste
- **THEN** el backend lo publica en el backplane y los paneles suscriptos a esa sesión/examen lo reciben

#### Scenario: Adaptador de backplane sustituible por el ganador de C-03
- **WHEN** C-03 determina el backplane ganador
- **THEN** la lógica de fan-out opera sobre ese adaptador sin cambios en la validación, persistencia ni contrato del evento

### Requirement: Propagación evento→panel p99 < 500 ms
El fan-out SHALL cumplir el SLO de propagación evento→panel de **p99 < 500 ms** bajo la carga objetivo (hasta el pico ~2.100 conc. / ~5.000 inserts/s, SU-06, `14`).

#### Scenario: Alerta de severidad alta propagada bajo 500 ms
- **WHEN** se ingesta un evento de severidad alta (p. ej. múltiples rostros)
- **THEN** el evento se propaga al panel del proctor en menos de 500 ms (p99)

### Requirement: Cero pérdida de eventos confirmados
El fan-out SHALL garantizar cero pérdida de eventos confirmados: un evento persistido SHALL terminar entregado a los paneles suscriptos, sin perderse ante reconexión de panel o redistribución de instancias (RN-CC-08).

#### Scenario: Evento confirmado no se pierde ante reconexión de panel
- **WHEN** un panel suscripto se reconecta mientras se ingestan eventos confirmados
- **THEN** ningún evento confirmado se pierde para ese panel tras la reconexión
