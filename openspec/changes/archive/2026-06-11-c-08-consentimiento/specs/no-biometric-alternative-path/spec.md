# Spec — no-biometric-alternative-path

> Vía alternativa de verificación sin biometría (escalación a proctor humano) para quien no consiente, garantizando que el consentimiento sea libre (RN-CO-05, RN-GLB-02, US-003 CA-4).

## ADDED Requirements

### Requirement: Vía alternativa sin biometría para quien no consiente
El sistema SHALL ofrecer al estudiante que no consiente la captura biométrica una vía alternativa de verificación de identidad sin biometría, escalando a un proctor humano en vivo, y SHALL NO abortar el examen por la falta de consentimiento (RN-CO-05, RN-GLB-02, US-003 CA-4).

#### Scenario: No consentir ofrece la vía alternativa
- **WHEN** un estudiante elige no consentir la verificación biométrica
- **THEN** el sistema le ofrece la verificación alternativa por proctor humano en lugar de bloquear el examen

#### Scenario: La elección de la vía alternativa escala a proctor
- **WHEN** el estudiante elige la vía alternativa
- **THEN** el sistema registra la elección y escala la verificación de identidad a un proctor humano

#### Scenario: La falta de consentimiento no aborta el examen
- **WHEN** el estudiante no consiente la biometría
- **THEN** el sistema no aborta abruptamente el examen y continúa por la vía alternativa
