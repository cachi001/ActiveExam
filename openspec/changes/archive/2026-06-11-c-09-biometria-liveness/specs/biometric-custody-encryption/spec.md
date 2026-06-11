# Spec — biometric-custody-encryption

> Cadena de custodia inicial del clip y persistencia cifrada at-rest del embedding, finalidad acotada, eliminado al egreso (RN-BIO-07/08, RN-CO-04, Ley 25.326).

## ADDED Requirements

### Requirement: Clip de verificación bajo cadena de custodia inicial
El sistema SHALL persistir el clip de verificación biométrica siguiendo la misma cadena de custodia que cualquier evidencia: hash y firma con la clave de sesión, subido por URL firmada directo al storage (RN-BIO-07, RN-CC-04, US-004 CA-6).

#### Scenario: El clip se sube con hash y firma por URL firmada
- **WHEN** el cliente captura el clip de verificación
- **THEN** el sistema lo hashea, lo firma con la clave de sesión y lo sube directo al storage por URL firmada, registrando la custodia inicial

### Requirement: Embedding persistido cifrado at-rest con finalidad acotada
El sistema SHALL persistir el embedding cifrado at-rest, con finalidad acotada exclusivamente a la verificación de identidad del examen, sin reutilización para otra finalidad, y marcado para eliminación al egreso del estudiante de la institución (RN-BIO-07, RN-BIO-08, RN-CO-04, Ley 25.326).

#### Scenario: El embedding se persiste cifrado
- **WHEN** se calcula y persiste el embedding del estudiante
- **THEN** el embedding queda cifrado at-rest y no se almacena en claro

#### Scenario: Finalidad acotada y eliminación al egreso
- **WHEN** se almacena un embedding biométrico
- **THEN** su uso queda restringido a la verificación de identidad y queda marcado para eliminación al egreso del estudiante
