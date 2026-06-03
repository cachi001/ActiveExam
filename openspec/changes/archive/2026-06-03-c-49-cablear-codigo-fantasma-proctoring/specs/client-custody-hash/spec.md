## ADDED Requirements

### Requirement: El payload del evento incluye SHA-256 del screenshot calculado en el cliente
El sistema SHALL calcular el `SHA-256` del screenshot antes de enviar el evento al backend. Cuando el screenshot está disponible (no null), el sistema SHALL convertir el base64 a `ArrayBuffer`, invocar `hashClip(arrayBuffer)` de `clipCustody.ts` y agregar el resultado como `screenshot_sha256_cliente: string` al payload del evento. Si el screenshot es null o la captura falla, el campo SHALL omitirse del payload sin errores.

#### Scenario: Hash calculado y agregado al payload
- **WHEN** se captura un frame del video al detectar un evento y el screenshot es válido
- **THEN** el payload enviado a `api.enviarEventoProctoring` incluye `screenshot_sha256_cliente` con el hash SHA-256 hex del screenshot
- **THEN** el hash tiene exactamente 64 caracteres hexadecimales en minúsculas

#### Scenario: Screenshot null — campo omitido
- **WHEN** `captureVideoFrame` retorna `null` (video no listo o sin stream)
- **THEN** el payload no incluye la clave `screenshot_sha256_cliente`
- **THEN** el evento se envía igual al backend sin interrupciones

#### Scenario: Error al calcular el hash — evento continúa
- **WHEN** `hashClip` lanza una excepción (crypto no disponible, buffer inválido)
- **THEN** el error se captura silenciosamente
- **THEN** el evento se envía sin `screenshot_sha256_cliente`
- **THEN** el flujo de examen continúa sin interrupción (L2.5: degradación silenciosa)

### Requirement: Deuda técnica documentada — firma HMAC y cadena de custodia completa fuera de alcance
El sistema SHALL documentar explícitamente en el código que la firma HMAC de eventos y la cadena de custodia completa (presigned PUT + EvidenceNotification) no se cablea porque el backend slim no valida la firma ni tiene endpoint `/evidence/presign`. Un comentario SHALL indicar el path de `eventSignature.ts` y `evidenceCapture.ts` como deuda técnica para cuando el backend implemente la validación.

#### Scenario: Comentario de deuda técnica visible en el código
- **WHEN** un desarrollador lee `useExamProctoring.ts`
- **THEN** existe un comentario que referencia `eventSignature.ts` y explica que la firma HMAC es deuda técnica pendiente de validación backend
