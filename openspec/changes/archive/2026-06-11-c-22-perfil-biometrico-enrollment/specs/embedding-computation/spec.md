# Spec — embedding-computation

> El embedding de referencia se calcula en el enrollment del perfil (reutilizable) y queda sujeto a vigencia/renovación (RN-BIO-01, US-004 CA-1).

## MODIFIED Requirements

### Requirement: Captura de video y cálculo del embedding facial
El sistema SHALL capturar en el cliente, durante el enrollment del Perfil, un video corto de 3–5 s con instrucciones claras y SHALL calcular el embedding facial de referencia del estudiante mediante Face Mesh sobre ese clip, reutilizando el motor de visión existente; el embedding de referencia resultante SHALL ser reutilizable entre rendiciones y SHALL quedar sujeto a vigencia y renovación, NO recapturándose por examen (RN-BIO-01, US-004 CA-1).

#### Scenario: Captura de 3–5 s con instrucciones claras en el perfil
- **WHEN** el estudiante inicia la captura de referencia biométrica en su Perfil
- **THEN** el sistema presenta instrucciones claras y captura un video de 3–5 s

#### Scenario: Cálculo del embedding de referencia sobre el clip
- **WHEN** el clip 3–5 s ha sido capturado en el perfil y el liveness es exitoso
- **THEN** el sistema calcula el embedding facial de referencia mediante Face Mesh sobre el clip y lo asocia al perfil con su vigencia

#### Scenario: El pre-examen verifica contra la referencia, no la recaptura
- **WHEN** un estudiante con embedding de referencia vigente inicia el pre-examen
- **THEN** el sistema verifica la identidad 1:1 contra el embedding de referencia del perfil sin recalcular una nueva referencia
