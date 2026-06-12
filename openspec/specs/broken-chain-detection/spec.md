# broken-chain-detection Specification

## Purpose
TBD - created by archiving change c-18-verificacion-cadena-apelacion. Update Purpose after archive.
## Requirements
### Requirement: Detección de cadena rota
El sistema SHALL detectar que la cadena está rota cuando cualquier hash recalculado no coincide o cualquier firma no valida, identificando la etapa de ruptura.

#### Scenario: Hash o firma alterados
- **WHEN** una etapa presenta un hash que no coincide o una firma inválida
- **THEN** el certificado marca la cadena como rota e identifica la etapa en la que se rompe

### Requirement: Evidencia no sostenida ante cadena rota
Cuando la cadena está rota, el certificado SHALL declarar que la evidencia no se sostiene.

#### Scenario: Veredicto de no sostenida
- **WHEN** la cadena resulta rota
- **THEN** el veredicto global del certificado es que la evidencia no se sostiene

### Requirement: Registro de la cadena rota
El sistema SHALL registrar en el audit log append-only el hecho de que una verificación detectó una cadena rota.

#### Scenario: Cadena rota registrada
- **WHEN** una verificación detecta una cadena rota
- **THEN** el hecho queda registrado en el audit log encadenado por hash

