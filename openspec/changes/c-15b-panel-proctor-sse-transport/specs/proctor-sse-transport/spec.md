# Spec — proctor-sse-transport

> Transporte SSE del panel (unidireccional, reconecta solo, **sin sticky**) alimentado por el backplane ganador de C-03, con reconexión transparente ante caída de instancia (DD-16). Implementado contra puertos abstractos.

## ADDED Requirements

### Requirement: Panel servido por SSE unidireccional sin sticky
El panel del proctor SHALL servirse por **SSE** (Server-Sent Events), un canal **unidireccional** servidor→panel que **reconecta solo**, **sin sticky sessions** (DD-16), detrás de un puerto `PanelTransportPort` cuyo adaptador es el ganador del concern (b) de C-03.

#### Scenario: El panel recibe eventos por SSE
- **WHEN** el proctor abre su panel y se suscribe a sus sesiones asignadas
- **THEN** el servidor le envía actualizaciones por un stream SSE unidireccional, sin requerir afinidad de sesión (sticky) a una instancia concreta

### Requirement: Fan-out vía backplane ganador de C-03
La propagación de eventos a los paneles SHALL pasar por un **backplane** detrás de `EventBackplanePort`, cuyo adaptador es el ganador del concern (c) de C-03 (Postgres `LISTEN/NOTIFY` o Redis Pub/Sub), de modo que **cualquier instancia** pueda servir a **cualquier panel**.

#### Scenario: Cualquier instancia sirve a cualquier panel
- **WHEN** un evento se publica en el backplane desde una instancia
- **THEN** cualquier instancia que tenga paneles suscriptos a esa sesión lo reenvía a sus paneles, sin depender de sticky sessions

### Requirement: Reconexión transparente ante caída de instancia
Ante la caída de la instancia que servía un panel, el panel SHALL **reconectar a otra instancia** sin perder su suscripción a las sesiones asignadas.

#### Scenario: Caída de instancia no deja al panel ciego
- **WHEN** la instancia FastAPI que servía un panel cae
- **THEN** el panel reconecta automáticamente a otra instancia y reanuda la recepción de eventos de sus sesiones asignadas, sin pérdida de suscripción
