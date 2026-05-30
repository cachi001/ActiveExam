# Spec — student-ws-channel

> Canal WebSocket bidireccional del estudiante: handshake autenticado, transporte de eventos/heartbeats/comandos y heartbeat firmado /5s (Flujo 3, US-007, DD-16, RN-HB-01). Es un canal **separado** del panel del proctor; el WebSocket bidireccional del estudiante es fijo, no está bajo la decisión de transporte de C-03.

## ADDED Requirements

### Requirement: Handshake autenticado con session_id, JWT y last_event_id
El canal SHALL establecer la conexión mediante un handshake que incluya `session_id`, un JWT válido y `last_event_id`. El JWT SHALL validarse en el handshake contra la clave pública de Keycloak (JWKS cacheado) — firma, expiración, audience e issuer (RN-AU-03) — y periódicamente durante la sesión.

#### Scenario: Handshake con JWT válido establece la conexión
- **WHEN** el cliente abre el WebSocket con `session_id`, un JWT válido y `last_event_id`
- **THEN** el backend valida el JWT contra el JWKS y acepta la conexión asociándola a la sesión

#### Scenario: Handshake con JWT inválido o expirado se rechaza
- **WHEN** el cliente abre el WebSocket con un JWT inválido o expirado
- **THEN** el backend rechaza la conexión en el handshake y no abre el canal

### Requirement: Canal bidireccional para eventos, heartbeats y comandos
El canal SHALL transportar eventos y heartbeats del cliente hacia el backend y comandos del backend hacia el cliente (bidireccional), separado del transporte del panel del proctor.

#### Scenario: Comando backend→cliente entregado por el mismo canal
- **WHEN** el backend emite un comando dirigido a la sesión del estudiante
- **THEN** el comando se entrega al cliente por el canal WebSocket bidireccional de esa sesión

### Requirement: Heartbeat firmado cada 5 segundos
El cliente SHALL enviar un heartbeat firmado con HMAC cada 5 segundos como prueba de vida de la sesión y del detector; el backend SHALL validar su firma (RN-HB-01).

#### Scenario: Heartbeat firmado recibido y validado periódicamente
- **WHEN** la sesión está activa
- **THEN** el cliente emite un heartbeat firmado cada 5 s y el backend valida su firma como prueba de vida

### Requirement: El canal no deriva sanciones automáticas
El canal SHALL limitarse a transportar y persistir señales; ninguna sanción ni decisión disciplinaria SHALL derivarse automáticamente de la ingesta (L2.5, RN-RV-07).

#### Scenario: Ingesta de evento crítico no produce sanción
- **WHEN** se ingesta un evento de severidad crítica (p. ej. posible cambio de identidad)
- **THEN** el sistema persiste y propaga la señal sin aplicar ninguna sanción automática
