# keycloak-federation-jit Specification

## Purpose
TBD - created by archiving change c-06-auth-rbac-keycloak. Update Purpose after archive.
## Requirements
### Requirement: Federación con el directorio institucional vía Keycloak
La autenticación SHALL delegarse en Keycloak (OAuth2/OIDC/SAML) federado con el directorio institucional, sin implementar autenticación propia (DD-09).

#### Scenario: Login institucional vía Keycloak
- **WHEN** un usuario inicia sesión con sus credenciales institucionales
- **THEN** la autenticación se resuelve en Keycloak (federación SAML/OIDC con el directorio) y el sistema recibe un JWT emitido por Keycloak (Flujo 1)

### Requirement: JIT provisioning del Usuario al primer login federado
El sistema SHALL provisionar el `Usuario` (C-05) **just-in-time** al primer login federado, tomando identificador institucional, roles y atributos federados, sin seed masivo de usuarios (`04` §Usuario).

#### Scenario: Primer login crea el Usuario
- **WHEN** un usuario federado inicia sesión por primera vez
- **THEN** se crea su entidad Usuario (C-05) con sus atributos federados, sin requerir un alta previa manual

#### Scenario: Logins posteriores reutilizan el Usuario
- **WHEN** un usuario ya provisionado vuelve a iniciar sesión
- **THEN** se reutiliza/actualiza su Usuario existente, sin crear duplicados

