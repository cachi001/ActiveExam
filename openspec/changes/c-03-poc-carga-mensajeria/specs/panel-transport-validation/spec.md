# Spec — panel-transport-validation (Concern b)

> Capacidad de **validación de carga** del **Concern (b) — transporte del panel del proctor**. Tiempo real (sub-500 ms). Hipótesis default = SSE + backplane sin sticky (A4, DD-16, IN-02). El canal del **estudiante** (WebSocket bidireccional) queda **fuera** de este concern: se modela solo como generador de carga.

## ADDED Requirements

### Requirement: Transporte del panel sin sticky sessions bajo redistribución de instancias
El transporte del panel SHALL sostener la suscripción de N=20–40 paneles al pico sin sticky sessions (SSE + backplane), de modo que la caída o redistribución de una instancia FastAPI no provoque pérdida de suscripción y la reconexión sea transparente, comparado contra la alternativa WebSocket + sticky.

#### Scenario: SSE reparte sin sticky y reconecta solo
- **WHEN** se ejecuta P2 con el panel sobre SSE + backplane y se redistribuyen/caen instancias FastAPI durante la corrida
- **THEN** ningún panel pierde su suscripción de forma permanente y la reconexión SSE es automática, sin requerir afinidad de instancia

#### Scenario: Comparación contra WebSocket + sticky
- **WHEN** se ejecuta el mismo escenario con el panel sobre WebSocket + sticky sessions
- **THEN** se registra el comportamiento de redistribución/reconexión y la concentración de conexiones por instancia para comparar contra SSE

### Requirement: Veredicto del concern (b) por métrica, default conservado por omisión
El concern (b) SHALL conservar SSE + backplane (A4) por omisión y promover WebSocket + sticky (SAD) **solo si** SSE no sostiene la redistribución de instancias o la reconexión transparente al pico, documentándolo como evolución condicionada y no como retrabajo (DD-19).

#### Scenario: Conservar SSE si sostiene la redistribución
- **WHEN** SSE + backplane sostiene la suscripción sin sticky y reconecta solo bajo caída de instancia al pico
- **THEN** el veredicto registra "conservar SSE + backplane (A4) ✓" con la evidencia que lo justifica

#### Scenario: Promover WebSocket+sticky solo si la métrica lo exige
- **WHEN** SSE no sostiene la redistribución sin pérdida de suscripción y WebSocket+sticky sí lo logra
- **THEN** el veredicto registra "promover WebSocket + sticky ✗" como evolución condicionada documentada
