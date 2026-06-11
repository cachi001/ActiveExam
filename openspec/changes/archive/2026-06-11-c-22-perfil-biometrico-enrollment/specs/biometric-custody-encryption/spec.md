# Spec — biometric-custody-encryption

> Además del embedding, se persiste la imagen de referencia del perfil como dato sensible (cifrada at-rest, finalidad acotada, eliminación al egreso, holds difieren), con metadato de vigencia (RN-BIO-07/08, RN-CO-04, Ley 25.326).

## MODIFIED Requirements

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

## ADDED Requirements

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
