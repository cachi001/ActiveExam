# Spec — exam-enrollment-with-consent

> Inscripción a un examen que captura el consentimiento informado completo en el momento de inscribirse (acción afirmativa, texto versionado, vía alternativa). Reordena el flujo de C-08 sin perder garantías legales.

## ADDED Requirements

### Requirement: La inscripción presenta el detalle del examen
El sistema SHALL presentar, antes de confirmar la inscripción, el detalle del examen (cátedra, fecha/hora, duración, modalidad de proctoring L2.5 y qué se monitorea) para que el estudiante decida informado.

#### Scenario: El estudiante ve el detalle antes de inscribirse
- **WHEN** un estudiante elige un examen disponible
- **THEN** el sistema muestra su detalle y qué se monitorea antes de pedir el consentimiento

### Requirement: El consentimiento informado se captura en la inscripción por acción afirmativa
El sistema SHALL capturar el consentimiento informado **durante la inscripción** mediante una acción afirmativa explícita sobre un texto versionado, sin casillas premarcadas; el sistema NO SHALL registrar la inscripción como consentida sin una acción afirmativa (RN-CO-01, RN-CO-02).

#### Scenario: Consentimiento con acción afirmativa habilita la inscripción
- **WHEN** el estudiante realiza la acción afirmativa sobre el texto versionado vigente
- **THEN** la inscripción queda registrada con el acuse (versión, timestamp, hash) y el estudiante queda habilitado para rendir

#### Scenario: Sin acción afirmativa no se confirma
- **WHEN** el estudiante no realiza la acción afirmativa
- **THEN** el control de confirmación permanece deshabilitado y no se registra consentimiento

### Requirement: Vía alternativa sin biometría disponible en la inscripción
El sistema SHALL ofrecer en la inscripción una vía alternativa sin biometría (verificación por proctor humano) para quien no consienta la biometría, dejándolo habilitado para rendir por esa vía (RN-CO-05).

#### Scenario: El estudiante elige la vía alternativa
- **WHEN** el estudiante opta por la vía alternativa sin biometría
- **THEN** la inscripción queda habilitada marcada para verificación por proctor humano, sin exigir captura biométrica
