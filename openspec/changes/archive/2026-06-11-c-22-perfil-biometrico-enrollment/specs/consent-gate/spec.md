# Spec — consent-gate

> El gate de consentimiento se resuelve al completar el perfil (enrollment), una sola vez, en lugar de antes de cada examen; se mantienen todas las garantías legales (RN-CO-01, DD-03).

## MODIFIED Requirements

### Requirement: Consentimiento es prerrequisito de la verificación biométrica
El sistema SHALL exigir un consentimiento válido registrado o la elección de la vía alternativa sin biometría antes de habilitar la captura de referencia biométrica del enrollment de perfil; un estudiante que no resolvió ninguno de los dos SHALL NO poder completar el enrollment ni quedar habilitado para inscribirse o rendir. El gate SHALL resolverse una sola vez al completar el perfil, NO antes de cada examen (RN-CO-01, DD-03).

#### Scenario: Con consentimiento válido se habilita la captura de referencia en el perfil
- **WHEN** un estudiante tiene un acuse de consentimiento válido registrado en su perfil
- **THEN** el sistema habilita la captura de referencia biométrica del enrollment

#### Scenario: Sin consentimiento ni vía alternativa, el enrollment no se habilita
- **WHEN** un estudiante no tiene consentimiento registrado ni eligió la vía alternativa en su perfil
- **THEN** el sistema no habilita la captura de referencia biométrica ni marca el perfil como completo

#### Scenario: Con vía alternativa elegida, la biometría no se exige
- **WHEN** un estudiante eligió la vía alternativa sin biometría en su perfil
- **THEN** el sistema no exige la captura de referencia biométrica y dirige la verificación al proctor humano

#### Scenario: El gate resuelto en el perfil aplica a todas las rendiciones
- **WHEN** un estudiante con consentimiento válido vigente en su perfil inicia el pre-examen de cualquier examen
- **THEN** el sistema no vuelve a solicitar el consentimiento y reutiliza el acuse de perfil para habilitar la rendición
