# Spec — evidence-capture-upload

> Etapa 1 de la cadena de custodia, en **zona no confiable**: captura del clip ante evento severo, hash SHA-256 + firma HMAC de sesión en el cliente, y upload directo a storage por URL firmada (RN-CC-01, RN-CC-04).

## ADDED Requirements

### Requirement: Captura de clip ante evento de severidad alta o crítica
El cliente SHALL capturar un clip de 5–10 s cuando, y solo cuando, se produce un evento de severidad **alta o crítica** (RN-CC-01); los eventos de severidad media o baseline NO disparan captura de evidencia.

#### Scenario: Evento severo dispara captura
- **WHEN** el detector emite un evento de severidad alta o crítica (p. ej. múltiples rostros, posible cambio de identidad)
- **THEN** el cliente captura un clip de 5–10 s asociado a ese evento

#### Scenario: Evento no severo no dispara captura
- **WHEN** el detector emite un evento de severidad media o baseline (p. ej. mirada desviada, heartbeat)
- **THEN** el cliente NO captura ningún clip de evidencia

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
