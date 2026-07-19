# pause-request-timeout Specification

## Purpose
TBD - created by archiving change c-72-integridad-rendicion-serverside. Update Purpose after archive.
## Requirements
### Requirement: El pedido de pausa sin responder expira por antigüedad

El sistema SHALL expirar toda solicitud de pausa en estado `'solicitada'` cuya antigüedad supere un umbral configurable (por env, con default conservador), transicionándola a un estado terminal (`'expirada'`) y sacándola de la cola de pausas pendientes del proctor. La expiración SHALL ser un acto del sistema que NO aprueba ni rechaza la pausa (L2.5, regla dura #5): NO SHALL abrir ventana de pausa ni setear `inicio_en`. Este timeout SHALL ser distinto de `pausa_max_min`, que limita la duración de una pausa ya aprobada.

#### Scenario: Pedido viejo sin responder expira

- **WHEN** una solicitud de pausa lleva `'solicitada'` más tiempo que el umbral y el proctor no la resolvió
- **THEN** la solicitud pasa a `'expirada'` y desaparece de la cola de pendientes del proctor

#### Scenario: Pedido reciente sigue pendiente

- **WHEN** una solicitud de pausa lleva `'solicitada'` menos tiempo que el umbral
- **THEN** la solicitud sigue pendiente y visible para el proctor

#### Scenario: La expiración no otorga la pausa

- **WHEN** una solicitud de pausa expira por antigüedad
- **THEN** no se abre ventana de pausa ni se registra `inicio_en`, y el estado terminal es `'expirada'`, no `'aprobada'`

### Requirement: Las pausas pendientes se cancelan al finalizar la sesión

El sistema SHALL cancelar (a `'expirada'`) toda solicitud de pausa `'solicitada'` de una sesión al finalizar esa sesión, sea la finalización manual o automática (auto-finalización). Una sesión cerrada SHALL NOT dejar pausas pendientes que ensucien el panel de supervisión en vivo.

#### Scenario: Finalización manual limpia las pausas pendientes

- **WHEN** un alumno finaliza manualmente su examen con una solicitud de pausa `'solicitada'` sin resolver
- **THEN** esa solicitud queda `'expirada'` y no aparece en la cola del proctor

#### Scenario: Auto-finalización limpia las pausas pendientes

- **WHEN** una sesión con una solicitud de pausa `'solicitada'` se auto-finaliza por vencimiento del deadline
- **THEN** esa solicitud queda `'expirada'`

#### Scenario: La cancelación es idempotente

- **WHEN** el mecanismo de expiración procesa dos veces una solicitud ya `'expirada'`
- **THEN** el estado no se re-muta y no se produce efecto adicional

