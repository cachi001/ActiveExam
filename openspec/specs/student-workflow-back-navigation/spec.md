# student-workflow-back-navigation Specification

## Purpose
TBD - created by archiving change c-66-ui-estudiante-onboarding-desktop. Update Purpose after archive.
## Requirements
### Requirement: Componente `BackButton` reutilizable

El sistema SHALL proveer un componente `BackButton` en `frontend/src/ui/components.tsx` con el patrón visual: `<Icon name="arrow_back" />` + label `Volver`, ubicado en la parte superior izquierda del contenido principal de la pantalla, con `onClick` configurable por screen.

#### Scenario: BackButton renderiza con icono + label
- **WHEN** se renderiza `<BackButton onClick={fn} />`
- **THEN** el DOM resultante contiene un `<button>` con el icono Material `arrow_back` y el texto `Volver`, accesible (con `aria-label` o texto visible)

#### Scenario: BackButton dispara onClick
- **WHEN** el usuario clickea el BackButton
- **THEN** se ejecuta el `onClick` provisto por la screen

### Requirement: BackButton presente en pantallas del workflow del estudiante

Las pantallas intermedias del workflow del estudiante SHALL incluir el `BackButton` en la parte superior, con navegación al paso lógico anterior: `Consent.tsx` → vuelve al dashboard; `EnrollmentConsentStep.tsx` → vuelve al dashboard; `EnrollmentBiometricStep.tsx` → vuelve a consent o al paso previo del enrollment; `EnrollmentDniStep.tsx` → vuelve al paso previo del enrollment.

#### Scenario: Consent.tsx tiene BackButton
- **WHEN** el estudiante está en `/consent`
- **THEN** la parte superior de la pantalla muestra `<BackButton>` que al clickearse navega al dashboard

#### Scenario: EnrollmentBiometricStep.tsx tiene BackButton
- **WHEN** el estudiante está en `/biometria` durante el enrollment
- **THEN** la parte superior muestra `<BackButton>` que navega al paso anterior del enrollment

### Requirement: Dashboard del estudiante NO tiene BackButton

La pantalla dashboard del estudiante (raíz del workflow) SHALL NOT mostrar el `BackButton` — para salir, el usuario usa el botón logout del header.

#### Scenario: Dashboard sin BackButton
- **WHEN** el estudiante está en el dashboard
- **THEN** no hay ningún `BackButton` en la pantalla

