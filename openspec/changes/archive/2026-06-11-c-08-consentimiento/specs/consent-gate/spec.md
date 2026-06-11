# Spec — consent-gate

> Gate que exige consentimiento válido (o elección de la vía alternativa) antes de habilitar la verificación biométrica de C-09 (RN-CO-01, DD-03).

## ADDED Requirements

### Requirement: Consentimiento es prerrequisito de la verificación biométrica
El sistema SHALL exigir un consentimiento válido registrado o la elección de la vía alternativa sin biometría antes de habilitar la captura y verificación biométrica; un estudiante que no resolvió ninguno de los dos SHALL NO poder avanzar a la verificación biométrica (RN-CO-01, DD-03).

#### Scenario: Con consentimiento válido se habilita la biometría
- **WHEN** un estudiante tiene un acuse de consentimiento válido registrado para el examen
- **THEN** el sistema habilita el paso de verificación biométrica

#### Scenario: Sin consentimiento ni vía alternativa, la biometría no se habilita
- **WHEN** un estudiante no tiene consentimiento registrado ni eligió la vía alternativa
- **THEN** el sistema no habilita la captura biométrica para ese estudiante

#### Scenario: Con vía alternativa elegida, la biometría no se exige
- **WHEN** un estudiante eligió la vía alternativa sin biometría
- **THEN** el sistema no exige la captura biométrica y dirige la verificación al proctor humano
