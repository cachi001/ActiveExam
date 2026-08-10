## ADDED Requirements

### Requirement: Allowlist de deployments Moodle confiables

El sistema SHALL persistir en `lti_deployment_confiable` qué combinaciones de `(iss, deployment_id, client_id)` son de confianza, junto con el JWKS URI del `iss` (para validar firmas entrantes) y, opcionalmente, el mapeo `context_id → comision_id`. Por defecto (tabla vacía) NINGÚN `iss` es confiable — el sistema MUST fallar cerrado.

#### Scenario: Tabla vacía rechaza todo

- **WHEN** no hay ninguna fila en `lti_deployment_confiable`
- **THEN** cualquier intento de `/lti/login` o `/lti/launch` es rechazado, sin excepción

#### Scenario: Alta de un deployment confiable

- **WHEN** un admin da de alta un `(iss, deployment_id, client_id)` con su JWKS URI
- **THEN** los launches subsiguientes desde ese deployment pueden validarse y aceptarse

### Requirement: Administración del allowlist (mínimo viable)

El sistema SHALL exponer un mecanismo admin-only (endpoint API; UI queda fuera del alcance mínimo de este change) para crear/editar/borrar filas de `lti_deployment_confiable`, incluyendo el mapeo `context_id → comision_id`. Solo `admin_sistema` SHALL poder gestionarlo.

#### Scenario: Admin gestiona el allowlist

- **WHEN** un usuario con rol `admin_sistema` crea o edita una fila de `lti_deployment_confiable`
- **THEN** el sistema persiste el cambio y los próximos launches lo reflejan

#### Scenario: Usuario sin rol admin_sistema intenta gestionar el allowlist

- **WHEN** un usuario sin rol `admin_sistema` intenta crear/editar/borrar una fila
- **THEN** el sistema responde 403
