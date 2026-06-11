# Spec — evidence-worm-storage

> Depósito del binario en bucket WORM (Object Lock modo **Compliance**) inmutable durante la retención, y descarga vía URL firmada con expiración (RN-CC-05, RN-CC-06, DD-07).

## ADDED Requirements

### Requirement: Depósito en bucket WORM con Object Lock modo Compliance
El backend SHALL depositar el binario de evidencia en un bucket con **Object Lock en modo Compliance**, de modo que el objeto sea **inmutable durante la retención** y no pueda ser modificado ni borrado por nadie, incluido el propietario de la cuenta (RN-CC-06, DD-07).

#### Scenario: Objeto inmutable durante la retención
- **WHEN** el binario se deposita en el bucket de evidencia con su retain-until
- **THEN** cualquier intento de modificar o borrar el objeto antes del retain-until es rechazado por el storage, incluso con credenciales privilegiadas

#### Scenario: Modo Compliance, no Governance
- **WHEN** se configura el Object Lock del bucket de evidencia
- **THEN** se usa el modo **Compliance** (sin override por rol privilegiado), no el modo Governance

### Requirement: Descarga de clip vía URL firmada con expiración
La descarga de un clip de evidencia SHALL realizarse mediante una URL firmada que **expira en 15 minutos** (RN-CC-05).

#### Scenario: URL de descarga firmada y caduca
- **WHEN** un consumidor autorizado solicita descargar un clip
- **THEN** el backend emite una URL firmada de GET con expiración de 15 min, y la URL deja de ser válida pasado ese plazo
