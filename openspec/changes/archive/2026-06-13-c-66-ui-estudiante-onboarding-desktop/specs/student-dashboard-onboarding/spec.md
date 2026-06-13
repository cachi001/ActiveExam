## ADDED Requirements

### Requirement: Dashboard inicial del estudiante con perfil incompleto

El dashboard del estudiante registrado SHALL mostrar como **primer render** la pantalla descripta en `captura.png` cuando `enrollment.perfil_completo === false`: header de la app + saludo `Hola, [Nombre] 👋` + email y institución del estudiante + card visible (color de advertencia) con título "Completá tu perfil antes de rendir", descripción de qué falta (consentimiento informado y/o captura biométrica) y CTA `Completar perfil` que navega al siguiente paso pendiente del onboarding.

#### Scenario: Estudiante registrado con perfil incompleto entra al dashboard
- **WHEN** un estudiante con `enrollment.perfil_completo === false` se loguea y aterriza en el dashboard
- **THEN** el primer render muestra: (a) el header de Active Exam con su nombre+id y botón logout, (b) saludo `Hola, [Nombre] 👋` con icono de ayuda, (c) email + institución `email · institución`, (d) card amarillo con `⚠️` + "Completá tu perfil antes de rendir" + lista de lo que falta + botón "Completar perfil"

#### Scenario: Estudiante con perfil completo entra al dashboard
- **WHEN** un estudiante con `enrollment.perfil_completo === true` se loguea y aterriza en el dashboard
- **THEN** el primer render muestra el header + saludo + email/institución + UI normal del dashboard (lista de exámenes habilitados, etc.) **sin** el card amarillo

#### Scenario: Card amarillo es visible al primer render sin scroll
- **WHEN** un estudiante con perfil incompleto entra al dashboard en pantalla 1366x768 (mínimo desktop común) o mobile
- **THEN** el card amarillo es visible sin necesidad de hacer scroll vertical desde el primer render

### Requirement: CTA del card amarillo navega al siguiente paso pendiente

El botón "Completar perfil" SHALL navegar al primer paso del onboarding que esté pendiente para ese estudiante: si falta consentimiento → `/consent`, si solo falta biometría → `/biometria`, etc.

#### Scenario: Falta consentimiento + biometría
- **WHEN** el estudiante con `consentimiento: null` y `biometria: null` hace click en "Completar perfil"
- **THEN** navega a `/consent`

#### Scenario: Solo falta biometría
- **WHEN** el estudiante con `consentimiento: válido` y `biometria: null` hace click en "Completar perfil"
- **THEN** navega a `/biometria`
