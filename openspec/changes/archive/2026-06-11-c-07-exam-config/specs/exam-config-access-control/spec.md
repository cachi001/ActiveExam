# Spec — exam-config-access-control

> Enforcement admin-only + MFA sobre toda la superficie de configuración del examen (RN-AU-05, RN-AU-07). Se apoya en el RBAC contextual de C-06, no lo reimplementa.

## ADDED Requirements

### Requirement: La configuración de examen es admin-only con MFA
El sistema SHALL restringir todos los endpoints de configuración de examen al rol administrador de exámenes con MFA satisfecho; cualquier otro rol o una sesión sin MFA SHALL recibir 403 (RN-AU-05, RN-AU-07).

#### Scenario: Administrador con MFA accede
- **WHEN** un administrador de exámenes con MFA satisfecho invoca cualquier endpoint de configuración de examen
- **THEN** el sistema autoriza la operación

#### Scenario: Rol no-admin es rechazado
- **WHEN** un usuario con rol distinto de administrador de exámenes (p. ej. estudiante o proctor) invoca un endpoint de configuración de examen
- **THEN** el sistema responde 403 y no ejecuta la operación

#### Scenario: Administrador sin MFA es rechazado
- **WHEN** un administrador de exámenes cuya sesión no satisface MFA invoca un endpoint de configuración de examen
- **THEN** el sistema responde 403 exigiendo MFA
