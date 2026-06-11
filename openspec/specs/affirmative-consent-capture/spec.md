# affirmative-consent-capture Specification

## Purpose
TBD - created by archiving change c-08-consentimiento. Update Purpose after archive.
## Requirements
### Requirement: Consentimiento por acción afirmativa explícita
El sistema SHALL requerir una acción afirmativa explícita e inequívoca del estudiante para registrar el consentimiento; SHALL NO presentar casillas premarcadas ni consentimiento por defecto, y SHALL rechazar en el backend cualquier intento de registrar un acuse sin acción afirmativa (RN-CO-02, US-003 CA-2).

#### Scenario: Consentimiento con acción afirmativa es aceptado
- **WHEN** el estudiante realiza la acción afirmativa explícita y envía el consentimiento
- **THEN** el sistema acepta y registra el acuse

#### Scenario: Registro sin acción afirmativa es rechazado en backend
- **WHEN** se intenta registrar un consentimiento sin la marca de acción afirmativa explícita
- **THEN** el sistema responde 422 y no persiste ningún acuse

#### Scenario: Sin casillas premarcadas
- **WHEN** se presenta la pantalla de consentimiento
- **THEN** ninguna opción de consentimiento aparece premarcada ni consentida por defecto

