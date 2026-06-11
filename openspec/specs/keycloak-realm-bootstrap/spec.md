# keycloak-realm-bootstrap Specification

## Purpose
TBD - created by archiving change c-52-keycloak-realm-config. Update Purpose after archive.
## Requirements
### Requirement: Realm proctoring importado automáticamente al arrancar

El sistema SHALL importar el realm `proctoring` al arrancar el contenedor Keycloak cuando no exista previamente en la base de datos. El import es idempotente: si el realm ya existe, Keycloak lo omite sin error.

#### Scenario: Primer arranque importa el realm
- **WHEN** el contenedor Keycloak arranca por primera vez (sin datos previos)
- **THEN** el realm `proctoring` existe en `http://localhost:8080/realms/proctoring` con metadata válida (realm name, enabled=true)

#### Scenario: Re-arranque no duplica el realm
- **WHEN** el contenedor Keycloak se reinicia con un realm `proctoring` ya importado en la BD
- **THEN** el realm sigue existiendo con la misma configuración (no se sobreescribe ni duplica)

---

### Requirement: Realm roles exactos que reconoce el backend

El realm `proctoring` SHALL contener exactamente los siguientes realm roles (nombres exactos, snake_case): `estudiante`, `proctor`, `admin_sistema`. Estos nombres coinciden con los valores del enum `Rol` del backend (`roles.py`).

#### Scenario: Roles presentes en el realm
- **WHEN** se consulta la lista de realm roles de `proctoring`
- **THEN** existen exactamente `estudiante`, `proctor`, `admin_sistema` (sin `admin_examenes` — no aplica al producto)

#### Scenario: Roles en token de usuario con rol asignado
- **WHEN** un usuario con rol `estudiante` obtiene un access token via password grant
- **THEN** el claim `realm_access.roles` del token contiene `"estudiante"`

---

### Requirement: Client SPA público con PKCE y audience mapper

El realm SHALL contener el client `proctoring-spa` configurado como cliente público OIDC con PKCE S256 obligatorio. El client SHALL tener un `oidc-audience-mapper` que inyecte `proctoring-api` en el claim `aud` del access token.

#### Scenario: Token contiene audience proctoring-api
- **WHEN** se solicita un access token para `proctoring-spa` via password grant
- **THEN** el claim `aud` del token contiene `"proctoring-api"`

#### Scenario: Issuer del token es localhost:8080
- **WHEN** se solicita un access token para cualquier client del realm `proctoring`
- **THEN** el claim `iss` del token es exactamente `"http://localhost:8080/realms/proctoring"`

#### Scenario: Backend acepta token con issuer y audience correctos
- **WHEN** el backend recibe un access token con `iss=http://localhost:8080/realms/proctoring` y `aud∋proctoring-api`
- **THEN** `TokenPolicy.principal_desde_claims()` no lanza `UnauthenticatedError` por issuer ni audiencia

---

### Requirement: Usuarios de prueba con password conocida

El realm SHALL contener 3 usuarios de prueba con email verificado y contraseña `test1234` (dev-only):
- `ecaceres` (Emiliano Cáceres, `ecaceres@frm.utn.edu.ar`) con rol `estudiante`.
- `cferreyra` (Carolina Ferreyra, `cferreyra@frm.utn.edu.ar`) con rol `proctor`.
- `admin` con rol `admin_sistema`.

#### Scenario: Login de usuario estudiante via password grant
- **WHEN** se hace POST al token endpoint con `username=ecaceres`, `password=test1234`, `client_id=proctoring-spa`, `grant_type=password`
- **THEN** la respuesta HTTP es 200 con un `access_token` válido

#### Scenario: Token del estudiante tiene rol correcto
- **WHEN** se decodifica el access token del usuario `ecaceres`
- **THEN** `realm_access.roles` contiene `"estudiante"` y NO contiene `"proctor"` ni `"admin_sistema"`

#### Scenario: Token del admin tiene rol administrativo
- **WHEN** se decodifica el access token del usuario `admin`
- **THEN** `realm_access.roles` contiene `"admin_sistema"`

---

### Requirement: MFA no satisfecho para usuarios de prueba (limitación documentada)

El sistema SHALL documentar que los usuarios de prueba no tienen OTP/WebAuthn configurado. El claim `amr` del access token emitido para estos usuarios NO DEBE incluir valores del conjunto `SEGUNDO_FACTOR_AMR`. El `AuthenticatedPrincipal` resultante MUST tener `mfa_satisfecho=False` para los roles `proctor` y `admin`. Los endpoints que exigen MFA MUST retornar 403 para estos usuarios hasta que se configure OTP manualmente en la UI de Keycloak.

#### Scenario: Token de proctor sin MFA genera principal con mfa_satisfecho=False
- **WHEN** se decodifica el token de `cferreyra` y se pasa a `TokenPolicy.principal_desde_claims()`
- **THEN** el `AuthenticatedPrincipal` resultante tiene `mfa_satisfecho=False`

#### Scenario: Token de estudiante sin MFA es aceptable (estudiante no requiere MFA)
- **WHEN** el backend procesa el token de `ecaceres`
- **THEN** `mfa_satisfecho=False` no bloquea el acceso a endpoints de estudiante (el backend solo exige MFA a `ROLES_CON_MFA`)

