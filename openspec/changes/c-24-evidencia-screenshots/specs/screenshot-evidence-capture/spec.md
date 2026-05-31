# Spec — screenshot-evidence-capture

> Captura de un **frame único** (screenshot) como artefacto de evidencia automática en el cliente (zona no confiable), reemplazando el clip de video. Conserva la cadena de custodia de origen (hash SHA-256 + firma HMAC de sesión + upload directo por URL firmada). Decisión DD-24-01.

## ADDED Requirements

### Requirement: Artefacto de evidencia es un screenshot, no un clip de video
El cliente SHALL capturar un **screenshot (frame único)** como artefacto de evidencia automática, en lugar de un clip de video de 5–10 s. El sistema NO SHALL capturar video continuo de la sesión bajo ninguna circunstancia (proporcionalidad L2.5, minimización de datos Ley 25.326).

#### Scenario: La captura automática produce un frame único
- **WHEN** corresponde capturar evidencia automática (por evento severo o por heartbeat)
- **THEN** el cliente captura **un único frame** (imagen) de la fuente correspondiente y NO graba video

#### Scenario: No se captura video continuo
- **WHEN** transcurre la sesión de examen sin disparadores de captura
- **THEN** el cliente NO graba ni almacena video continuo de la sesión

### Requirement: Hash SHA-256 y firma HMAC de sesión del screenshot en el cliente
El cliente SHALL calcular el **SHA-256** del screenshot y **firmarlo con HMAC usando la clave de sesión rotativa** antes de subirlo (etapa 1 de la cadena de custodia, RN-CC-02); el hash y la firma se envían como metadata al backend.

#### Scenario: Screenshot hasheado y firmado en origen
- **WHEN** el cliente termina de capturar el screenshot
- **THEN** calcula `hash_cliente = SHA-256(screenshot)` y `firma_cliente = HMAC(clave_sesion, hash_cliente)` y los adjunta a la notificación de evidencia

### Requirement: Upload directo del screenshot a storage por URL firmada
El binario del screenshot SHALL subirse **directo al storage** mediante una URL firmada de PUT, sin pasar por el backend (RN-CC-04); el backend solo recibe la metadata, el hash y la firma.

#### Scenario: Subida directa por presigned URL
- **WHEN** el cliente solicita subir un screenshot de evidencia
- **THEN** el backend emite una URL firmada de PUT y el cliente sube la imagen directamente al storage por esa URL, sin que el binario transite por el backend

### Requirement: Re-inferencia server-side estática sobre el frame
El worker server-side SHALL re-ejecutar la inferencia **sobre el frame estático** (detección de rostros/objetos en la imagen) y comparar con lo reportado por el cliente, firmando el resultado sobre el screenshot exacto como cuarta etapa de la cadena de custodia. La re-inferencia NO SHALL asumir contexto temporal (no hay secuencia de frames), aceptando explícitamente la pérdida de re-inferencia temporal como tradeoff L2.5 (DD-24-01).

#### Scenario: Re-inferencia estática y comparación forense
- **WHEN** el worker re-descarga un screenshot de evidencia tras la verificación de hash
- **THEN** re-ejecuta la detección sobre el frame, compara labels/confidences con lo reportado por el cliente, y firma el resultado sobre ese screenshot; una discrepancia es señal forense de posible tampering

#### Scenario: La evidencia es insumo para revisión humana, no veredicto automático
- **WHEN** la re-inferencia estática detecta una discrepancia o confirma el evento
- **THEN** el resultado se adjunta como evidencia para **revisión humana** y NO dispara ninguna sanción automática (L2.5)
