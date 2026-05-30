# Spec — independent-expert-verification

> El certificado debe ser validable por un perito externo de forma independiente (DD-07, RN-CC-07).

## ADDED Requirements

### Requirement: Certificado autoportante para verificación independiente
El certificado SHALL contener, por etapa, el hash, la firma, el algoritmo y la clave pública necesaria (la clave maestra para la etapa del worker), junto con los identificadores de la evidencia, de modo que un perito externo pueda validar la cadena sin invocar el sistema emisor.

#### Scenario: Perito valida con la clave pública
- **WHEN** un perito externo recibe el certificado
- **THEN** puede recomputar los hashes y verificar las firmas con herramientas estándar usando la clave pública maestra, sin llamar a la API

#### Scenario: Certificado sin datos personales
- **WHEN** se inspecciona el certificado
- **THEN** contiene hashes, firmas y claves públicas, y NO contiene el contenido del clip ni datos personales
