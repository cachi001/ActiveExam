# Tasks — C-17 `dsr-derechos-titular`

> Backend FastAPI, Clean/Hexagonal. Cada tarea con Done verificable. TDD: el test se escribe antes o junto a la implementación.

## 1. Endpoint y enrutamiento DSR (capability `dsr-rights-endpoint`)

- [ ] 1.1 Definir el enum `dsr_type` {access, rectification, erasure, portability} y el adaptador HTTP `POST /api/v1/dsr/{type}` que valida `{type}` y autentica al titular vía Keycloak (C-06); Done: endpoint responde 404/422 a tipos inválidos y 401 sin auth
- [ ] 1.2 Definir el puerto de aplicación `DsrUseCase` y el enrutado por tipo hacia los casos de uso de dominio; Done: cada `{type}` despacha a su caso de uso, sin lógica HTTP en el dominio
- [ ] 1.3 Implementar `access`: devuelve el conjunto de datos personales del titular (metadatos de sesiones, eventos, evidencia asociada, embeddings, consentimientos) en formato legible; Done: respuesta incluye los datos del titular y excluye datos de terceros
- [ ] 1.4 Implementar `rectification`: corrige datos personales rectificables del titular y registra la corrección; Done: el dato queda corregido y se genera entrada de audit log
- [ ] 1.5 Implementar `portability`: exporta los datos del titular en formato estructurado de lectura mecánica (JSON); Done: export válido, estructurado, solo del titular
- [ ] 1.6 Garantizar respuesta en plazo legal configurable; las operaciones diferidas se marcan pendientes con causa; Done: respuesta dentro del plazo configurado; diferidas en estado `pendiente`

## 2. Derecho al olvido con holds (capability `dsr-erasure-with-holds`)

- [ ] 2.1 Implementar `HoldVerifier`: consulta casos disciplinarios abiertos vinculados al titular (sesión → evidencia → caso); Done: devuelve true/false y la lista de casos que imponen hold
- [ ] 2.2 Implementar `erasure` SIN holds: elimina embeddings cifrados, revoca acceso al binario (purga física diferida a la expiración del Object Lock, registrada) y anonimiza registros dejando residual sin datos personales (RN-DSR-03); Done: embeddings borrados, residual sin PII, purga diferida registrada
- [ ] 2.3 Implementar `erasure` CON holds: difiere la eliminación, no borra nada, informa el motivo legal y deja la solicitud pendiente hasta cerrar el caso (Flujo 9 caso de error); Done: nada se borra, estado `diferida`, causa registrada
- [ ] 2.4 Implementar el `Anonymizer`: sustituye identificadores personales por seudónimo irreversible en sesiones/eventos/consentimientos, conservando residual probatorio sin PII; Done: residual verificable sin datos personales reidentificables
- [ ] 2.5 Documentar/referenciar que la oposición a decisiones automatizadas (RN-DSR-04) está cubierta por arquitectura (ninguna sanción automática, L2.5); Done: nota en el contrato del endpoint, sin acción de borrado asociada

## 3. Trazabilidad y auditoría (capability `dsr-auditability`)

- [ ] 3.1 Generar entradas en el audit log append-only para toda operación DSR (actor=titular, acción=dsr.{type}, propósito, timestamp, encadenadas por hash); Done: cada operación deja rastro encadenado
- [ ] 3.2 Garantizar que el audit log registra el resultado (ejecutada/diferida) sin reexponer datos personales eliminados; Done: la entrada no contiene PII borrada
- [ ] 3.3 Verificar que la operación es reconstruible en auditoría a partir del audit log + residual; Done: una auditoría puede demostrar que la eliminación ocurrió y cuándo

## 4. Tests

- [ ] 4.1 Test: eliminación SIN holds borra binarios (referencia/acceso) y embeddings y deja residual sin PII; Done: test verde
- [ ] 4.2 Test: eliminación CON hold (caso abierto) se difiere y no borra nada; Done: test verde
- [ ] 4.3 Test: anonimización produce un residual sin datos personales reidentificables; Done: test verde
- [ ] 4.4 Test: portabilidad exporta los datos del titular en formato estructurado y excluye terceros; Done: test verde
- [ ] 4.5 Test: respuesta dentro del plazo legal configurado; diferidas marcadas pendientes; Done: test verde
- [ ] 4.6 Test: trazabilidad — cada operación DSR genera entradas en el audit log append-only sin PII eliminada; Done: test verde
