# Spec — immutable-consent-record

> Persistencia inmutable del acuse de consentimiento (`Consentimiento`: user_id, exam_id, versión_texto, timestamp, hash), no modificable ni borrable (RN-CO-01, US-003 CA-3).

## ADDED Requirements

### Requirement: Registro inmutable del acuse con timestamp y hash
El sistema SHALL persistir el acuse de consentimiento como un registro `Consentimiento` con user_id, exam_id, versión del texto, timestamp y hash del texto exacto consentido; el registro SHALL ser inmutable y SHALL rechazar cualquier UPDATE o DELETE (RN-CO-01, US-003 CA-3).

#### Scenario: El acuse se persiste con timestamp y hash
- **WHEN** un estudiante consiente con acción afirmativa
- **THEN** el sistema crea un registro `Consentimiento` con user_id, exam_id, versión_texto, timestamp y hash del texto consentido

#### Scenario: El acuse no puede modificarse
- **WHEN** se intenta actualizar un registro de consentimiento existente
- **THEN** el sistema rechaza la operación y el acuse permanece inalterado

#### Scenario: El acuse no puede borrarse
- **WHEN** se intenta eliminar un registro de consentimiento existente
- **THEN** el sistema rechaza la operación y el acuse permanece persistido

#### Scenario: El hash sella el texto exacto consentido
- **WHEN** se audita un acuse meses después
- **THEN** el hash permite verificar que el texto consentido corresponde exactamente a la versión registrada
