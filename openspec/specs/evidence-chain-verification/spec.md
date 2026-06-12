# evidence-chain-verification Specification

## Purpose
TBD - created by archiving change c-18-verificacion-cadena-apelacion. Update Purpose after archive.
## Requirements
### Requirement: Endpoint de verificación de cadena en apelación
El sistema SHALL exponer `POST /api/v1/evidence/{id}/verify-chain` que, para una evidencia dada, re-verifica las cuatro etapas de la cadena de custodia y emite un certificado de verificación.

#### Scenario: Evidencia existente verificada
- **WHEN** se invoca `verify-chain` sobre una evidencia existente
- **THEN** el sistema re-verifica las cuatro etapas y emite un certificado con el resultado de cada una

#### Scenario: Evidencia inexistente
- **WHEN** se invoca `verify-chain` sobre un id de evidencia inexistente
- **THEN** el sistema responde con un error de recurso no encontrado

### Requirement: Verificación de las cuatro etapas de la cadena
El certificado SHALL reportar el resultado de cada etapa: (1) hash y firma HMAC del cliente, (2) re-hash y firma del backend, (3) firma maestra asimétrica del worker, (4) coherencia del output de re-inferencia firmado.

#### Scenario: Resultado por etapa
- **WHEN** se genera el certificado de una cadena íntegra
- **THEN** las cuatro etapas figuran como verificadas y el veredicto global es que la evidencia se sostiene

#### Scenario: Material de una etapa no disponible
- **WHEN** la clave de sesión de la etapa cliente no está disponible
- **THEN** el certificado distingue esa etapa como no verificable y sostiene el resultado en las etapas restantes

### Requirement: Verificación de solo lectura sobre evidencia WORM
La verificación SHALL ser de solo lectura y NO SHALL mutar la evidencia ni su cadena de custodia.

#### Scenario: Evidencia intacta tras verificar
- **WHEN** se ejecuta `verify-chain`
- **THEN** la evidencia y su cadena permanecen sin modificación

