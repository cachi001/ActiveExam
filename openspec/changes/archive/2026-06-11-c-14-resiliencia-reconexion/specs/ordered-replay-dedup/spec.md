# Spec — ordered-replay-dedup

> Drenaje del buffer en orden y deduplicación por `event_id` que garantizan exactly-once lógico (RN-HB-03, Flujo 5). La deduplicación se cierra contra la persistencia de C-10.

## ADDED Requirements

### Requirement: Drenaje del buffer en orden al reconectar
Al reconectar, el cliente SHALL drenar el buffer IndexedDB reenviando los eventos pendientes **en orden**, sin alterar la secuencia en que fueron producidos.

#### Scenario: Eventos del buffer se reenvían en orden
- **WHEN** el cliente reconecta con eventos pendientes en el buffer
- **THEN** los reenvía en el mismo orden en que fueron producidos

### Requirement: Deduplicación por event_id (exactly-once lógico)
El backend SHALL deduplicar por `event_id`: un evento ya persistido que se reenvía SHALL NOT producir un duplicado, garantizando exactly-once lógico (ni pérdida ni duplicados) (RN-HB-03).

#### Scenario: Reenvío de un evento ya persistido no genera duplicado
- **WHEN** el cliente reenvía un evento cuyo `event_id` ya fue persistido
- **THEN** el backend lo reconoce como duplicado y no crea una segunda fila

#### Scenario: Replay completo sin pérdida ni duplicados
- **WHEN** se reenvía el buffer completo tras una reconexión que solapa eventos ya confirmados con eventos nuevos
- **THEN** todos los eventos nuevos quedan persistidos exactamente una vez y ninguno se duplica ni se pierde
