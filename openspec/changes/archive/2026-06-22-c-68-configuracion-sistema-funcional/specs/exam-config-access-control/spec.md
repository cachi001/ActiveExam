# exam-config-access-control

## ADDED Requirements

### Requirement: La configuración global del sistema es admin_sistema-only con MFA
El sistema SHALL restringir todos los endpoints de **edición de la configuración global del sistema** al rol `admin_sistema` con MFA satisfecho; cualquier otro rol o una sesión sin MFA SHALL recibir 403 (RN-AU-05). La lectura de la configuración efectiva (`GET /api/v1/config/effective`) SHALL estar disponible para cualquier usuario autenticado.

#### Scenario: admin_sistema con MFA edita la config global
- **WHEN** un `admin_sistema` con MFA satisfecho invoca un endpoint de edición de configuración global
- **THEN** el sistema autoriza la operación

#### Scenario: Rol no-admin_sistema es rechazado en edición
- **WHEN** un usuario con rol distinto de `admin_sistema` (p. ej. `admin_examenes`, proctor o estudiante) invoca un endpoint de edición de configuración global
- **THEN** el sistema responde 403 y no ejecuta la operación

#### Scenario: Lectura de config efectiva para cualquier autenticado
- **WHEN** un usuario autenticado de cualquier rol llama a `GET /api/v1/config/effective`
- **THEN** el sistema retorna la configuración efectiva sin exigir `admin_sistema`
