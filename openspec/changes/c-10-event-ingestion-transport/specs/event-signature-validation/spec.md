# Spec — event-signature-validation

> Validación server-side de la firma HMAC de cada evento y heartbeat antes de persistir, con rechazo del no firmado o inválido (RN-GLB-01 zero trust, RN-EV-05, RN-HB-01). El cliente es sensor no confiable; la versión confiable es la del servidor.

## ADDED Requirements

### Requirement: Validación de firma HMAC de cada evento antes de persistir
El backend SHALL validar la firma HMAC-SHA256 de cada evento contra la clave de sesión rotativa **antes** de persistirlo en la hypertable. Un evento cuya firma no valide SHALL ser rechazado y no persistido.

#### Scenario: Evento con firma válida se acepta para persistir
- **WHEN** llega un evento cuya firma HMAC valida contra la clave de la sesión
- **THEN** el backend lo acepta y procede a persistirlo

#### Scenario: Evento con firma inválida se rechaza
- **WHEN** llega un evento cuya firma HMAC no valida contra la clave de la sesión
- **THEN** el backend lo rechaza, no lo persiste y registra el rechazo

### Requirement: Rechazo del evento no firmado
El backend SHALL rechazar todo evento que llegue sin firma; un evento sin firma SHALL NOT ser persistido ni propagado.

#### Scenario: Evento sin firma no se persiste ni propaga
- **WHEN** llega un evento sin el campo `firma`
- **THEN** el backend lo rechaza sin persistirlo ni propagarlo a los paneles

### Requirement: Validación de la firma del heartbeat
El backend SHALL validar la firma HMAC de cada heartbeat; un heartbeat con firma inválida SHALL NOT contar como prueba de vida válida.

#### Scenario: Heartbeat con firma inválida no cuenta como prueba de vida
- **WHEN** llega un heartbeat cuya firma HMAC no valida
- **THEN** el backend no lo computa como prueba de vida válida de la sesión

### Requirement: Re-firma server-side como versión confiable
El backend SHALL tratar el evento entrante como entrada potencialmente hostil y SHALL producir la versión confiable server-side (re-inferencia/re-firma donde corresponda), de modo que la fuente de verdad sea el servidor y no el cliente (RN-GLB-01).

#### Scenario: La versión persistida es la verificada server-side
- **WHEN** un evento validado se persiste
- **THEN** lo que queda como fuente de verdad es la versión verificada y firmada server-side, no la cruda reportada por el cliente
