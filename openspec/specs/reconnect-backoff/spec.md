# reconnect-backoff Specification

## Purpose
TBD - created by archiving change c-14-resiliencia-reconexion. Update Purpose after archive.
## Requirements
### Requirement: Reconexión con backoff exponencial y jitter del 20%
Ante la caída del WebSocket, el cliente SHALL reconectar usando backoff exponencial con jitter del 20% para evitar el "thundering herd" de reconexiones simultáneas (RN-HB-05).

#### Scenario: Reintentos con intervalos crecientes y jitter
- **WHEN** el WebSocket cae y el cliente intenta reconectar varias veces
- **THEN** los intervalos entre reintentos crecen exponencialmente y se aleatorizan con un jitter del 20%

#### Scenario: Muchos clientes no reconectan al unísono
- **WHEN** un corte de red afecta a muchos clientes a la vez
- **THEN** el jitter distribuye sus reintentos en el tiempo, evitando un pico simultáneo de reconexiones

### Requirement: Handshake de reconexión con last_event_id
El cliente SHALL reconectar enviando en el handshake el `last_event_id` confirmado, para que el backend pueda reenviar los eventos faltantes posteriores a ese id.

#### Scenario: Reconexión envía el último id confirmado
- **WHEN** el cliente reconecta tras un corte
- **THEN** el handshake incluye el `last_event_id` confirmado y el backend reenvía los eventos posteriores a ese id

