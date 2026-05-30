# Spec — pre-exam-verification-wizard

> Wizard pre-examen unificado que solo verifica (requisitos + biometría + sala de espera). El consentimiento ya fue resuelto en la inscripción, por lo que el wizard NO lo re-solicita.

## ADDED Requirements

### Requirement: El wizard pre-examen solo verifica, no pide consentimiento
El día del examen, el sistema SHALL presentar un único wizard de verificación con los pasos: chequeo de requisitos de equipo, verificación biométrica/liveness y sala de espera; el wizard NO SHALL presentar una pantalla de consentimiento, porque el consentimiento se resolvió en la inscripción.

#### Scenario: El estudiante habilitado verifica sin consentir de nuevo
- **WHEN** un estudiante habilitado (inscripto y consentido) inicia el wizard pre-examen
- **THEN** el wizard ejecuta requisitos → biometría → sala de espera sin presentar consentimiento

#### Scenario: Indicador de pasos honesto
- **WHEN** el wizard avanza entre pasos
- **THEN** el indicador refleja los pasos reales del wizard de verificación y no un conteo heredado del flujo anterior

### Requirement: Gate de habilitación previo al wizard
El sistema SHALL permitir iniciar el wizard solo si el estudiante está habilitado para ese examen (inscripto con consentimiento resuelto); en caso contrario SHALL derivarlo a inscribirse.

#### Scenario: Estudiante no habilitado es derivado a inscribirse
- **WHEN** un estudiante no inscripto o sin consentimiento resuelto intenta rendir
- **THEN** el sistema lo deriva al dashboard a inscribirse en vez de abrir el wizard

#### Scenario: Vía alternativa saltea la biometría
- **WHEN** el estudiante se habilitó por la vía alternativa sin biometría
- **THEN** el wizard omite el paso biométrico e indica verificación por proctor humano
