# Spec — student-exam-dashboard

> Dashboard del estudiante: punto de aterrizaje tras el login que da panorama de exámenes disponibles e inscripciones, con la acción siguiente de cada uno (capa de presentación de demo sobre la API mock).

## ADDED Requirements

### Requirement: El estudiante aterriza en un dashboard con exámenes e inscripciones
Tras autenticarse como estudiante, el sistema SHALL presentar un dashboard con (a) los exámenes disponibles para inscribirse y (b) las inscripciones del estudiante con su estado actual; el estudiante NO SHALL ser dirigido directamente al chequeo de requisitos sin pasar por el dashboard.

#### Scenario: Estudiante autenticado ve su dashboard
- **WHEN** un estudiante inicia sesión
- **THEN** el sistema muestra "Exámenes disponibles" y "Mis inscripciones" en vez de iniciar el pre-examen

#### Scenario: Cada inscripción muestra su acción siguiente
- **WHEN** el dashboard lista una inscripción
- **THEN** muestra su estado (inscripto / consentimiento pendiente / habilitado para rendir / rendido) y la acción siguiente correspondiente (Inscribirse, Continuar consentimiento, Rendir o ninguna)

#### Scenario: Sin exámenes ni inscripciones
- **WHEN** no hay exámenes disponibles ni inscripciones
- **THEN** el dashboard muestra un estado vacío claro en lugar de un área en blanco
