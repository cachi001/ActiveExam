# Spec — embedding-computation

> Cálculo del embedding facial (Face Mesh) sobre el clip 3–5 s en el cliente (RN-BIO-01, US-004 CA-1).

## ADDED Requirements

### Requirement: Captura de video y cálculo del embedding facial
El sistema SHALL capturar en el cliente un video corto de 3–5 s con instrucciones claras y SHALL calcular el embedding facial del estudiante mediante Face Mesh sobre ese clip (RN-BIO-01, US-004 CA-1).

#### Scenario: Captura de 3–5 s con instrucciones claras
- **WHEN** el estudiante inicia la verificación de identidad
- **THEN** el sistema presenta instrucciones claras y captura un video de 3–5 s

#### Scenario: Cálculo del embedding sobre el clip
- **WHEN** el clip 3–5 s ha sido capturado y el liveness es exitoso
- **THEN** el sistema calcula el embedding facial mediante Face Mesh sobre el clip
