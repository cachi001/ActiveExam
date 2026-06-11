# evidence-capture-upload Specification

## Purpose
TBD - created by archiving change c-12-evidencia-cadena-custodia. Update Purpose after archive.
## Requirements
### Requirement: Captura de clip ante evento de severidad alta o crítica
El cliente SHALL capturar un **screenshot (frame único)** cuando, y solo cuando, se produce un evento de severidad **alta o crítica** (RN-CC-01); los eventos de severidad media o baseline NO disparan captura de evidencia. El artefacto deja de ser un clip de video de 5–10 s y pasa a ser una captura de un único frame (proporcionalidad L2.5, minimización de datos), aceptando explícitamente la pérdida de re-inferencia temporal y de re-verificación de liveness/movimiento sobre la evidencia (DD-24-01).

#### Scenario: Evento severo dispara captura
- **WHEN** el detector emite un evento de severidad alta o crítica (p. ej. múltiples rostros, posible cambio de identidad)
- **THEN** el cliente captura un **screenshot (frame único)** asociado a ese evento

#### Scenario: Evento no severo no dispara captura
- **WHEN** el detector emite un evento de severidad media o baseline (p. ej. mirada desviada, heartbeat de eventos)
- **THEN** el cliente NO captura ningún screenshot de evidencia por este mecanismo

#### Scenario: No se captura video continuo ni clips
- **WHEN** transcurre la sesión de examen
- **THEN** el cliente NO graba video continuo ni clips de 5–10 s; la evidencia automática es siempre un frame único

### Requirement: Hash SHA-256 y firma HMAC de sesión en el cliente
El cliente SHALL calcular el **SHA-256** del clip y **firmarlo con HMAC usando la clave de sesión rotativa** antes de subirlo (etapa 1, RN-CC-02); el hash y la firma se envían como metadata al backend.

#### Scenario: Clip hasheado y firmado en origen
- **WHEN** el cliente termina de capturar el clip
- **THEN** calcula `hash_cliente = SHA-256(clip)` y `firma_cliente = HMAC(clave_sesion, hash_cliente)` y los adjunta a la notificación de evidencia

### Requirement: Upload directo a storage por URL firmada
El binario del clip SHALL subirse **directo al storage** mediante una URL firmada de PUT, sin pasar por el backend (RN-CC-04); el backend solo recibe la metadata, el hash y la firma.

#### Scenario: Subida directa por presigned URL
- **WHEN** el cliente solicita subir un clip de evidencia
- **THEN** el backend emite una URL firmada de PUT y el cliente sube el binario directamente al storage por esa URL, sin que el binario transite por el backend

#### Scenario: El clip de verificación biométrica sigue la misma cadena
- **WHEN** se captura el clip de la verificación biométrica de identidad
- **THEN** sigue exactamente la misma cadena de custodia que cualquier otra evidencia (hash + firma + upload directo)

