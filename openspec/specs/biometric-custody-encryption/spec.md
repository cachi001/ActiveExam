# biometric-custody-encryption Specification

## Purpose
TBD - created by archiving change c-09-biometria-liveness. Update Purpose after archive.
## Requirements
### Requirement: Clip de verificación bajo cadena de custodia inicial
El sistema SHALL persistir el clip de verificación biométrica siguiendo la misma cadena de custodia que cualquier evidencia: hash y firma con la clave de sesión, subido por URL firmada directo al storage (RN-BIO-07, RN-CC-04, US-004 CA-6).

#### Scenario: El clip se sube con hash y firma por URL firmada
- **WHEN** el cliente captura el clip de verificación
- **THEN** el sistema lo hashea, lo firma con la clave de sesión y lo sube directo al storage por URL firmada, registrando la custodia inicial

### Requirement: Embedding persistido cifrado at-rest con finalidad acotada
El sistema SHALL persistir el embedding de referencia cifrado at-rest, con finalidad acotada exclusivamente a la verificación de identidad del estudiante, sin reutilización para otra finalidad, marcado para eliminación al egreso del estudiante de la institución, y acompañado de metadatos de vigencia (fecha de captura, fecha de expiración, versión). Los holds legales SHALL diferir esa eliminación (RN-BIO-07, RN-BIO-08, RN-CO-04, Ley 25.326).

#### Scenario: El embedding se persiste cifrado
- **WHEN** se calcula y persiste el embedding de referencia del estudiante
- **THEN** el embedding queda cifrado at-rest y no se almacena en claro

#### Scenario: Finalidad acotada y eliminación al egreso
- **WHEN** se almacena un embedding de referencia biométrico
- **THEN** su uso queda restringido a la verificación de identidad y queda marcado para eliminación al egreso del estudiante

#### Scenario: El embedding lleva metadatos de vigencia
- **WHEN** se persiste el embedding de referencia
- **THEN** el sistema registra su fecha de captura, fecha de expiración y versión junto al embedding

### Requirement: Imagen de referencia del perfil persistida cifrada como dato sensible
El sistema SHALL persistir la imagen de referencia capturada en el enrollment del perfil como dato sensible: cifrada at-rest, con finalidad acotada a la verificación de identidad y la revisión humana, marcada para eliminación al egreso del estudiante, con metadatos de vigencia (fecha de captura, fecha de expiración, versión) y diferida por holds legales (RN-BIO-07, RN-BIO-08, RN-CO-04, Ley 25.326).

#### Scenario: La imagen de referencia se persiste cifrada
- **WHEN** un estudiante completa la captura de referencia biométrica en su perfil
- **THEN** el sistema persiste la imagen de referencia cifrada at-rest y no en claro

#### Scenario: Finalidad acotada y eliminación al egreso de la imagen de referencia
- **WHEN** se almacena una imagen de referencia del perfil
- **THEN** su uso queda restringido a la verificación de identidad y la revisión humana, y queda marcada para eliminación al egreso del estudiante

#### Scenario: Un hold legal difiere la eliminación de la imagen de referencia
- **WHEN** existe un hold legal vigente sobre el estudiante al momento de su egreso
- **THEN** el sistema difiere la eliminación de la imagen de referencia hasta que el hold se levante

