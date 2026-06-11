# jwt-own-issuer Specification

## Purpose
TBD - created by archiving change c-55-auth-provider-jwt-propio. Update Purpose after archive.
## Requirements
### Requirement: Emisión de JWT propio en formato compatible con TokenPolicy
El backend SHALL emitir access tokens JWT firmados con HS256 usando `JWT_OWN_SECRET` (256+ bits, env/Vault), con claims compatibles con `TokenPolicy.principal_desde_claims()`: `sub`, `preferred_username`, `email`, `realm_access.roles`, `iss` (= `JWT_OWN_ISSUER`), `aud` (= `JWT_AUDIENCE`), `exp`, `iat`. El TTL SHALL ser configurable (`access_token_ttl_seconds`, mínimo 900 s).

#### Scenario: Emisión correcta en login exitoso
- **WHEN** el endpoint `POST /api/v1/auth/login` recibe credenciales válidas
- **THEN** responde con un JWT firmado HS256 con todos los claims requeridos, `exp` = `iat + access_token_ttl_seconds`, y un refresh token rotativo

#### Scenario: Token emitido es aceptado por el validador
- **WHEN** un cliente presenta en Authorization el JWT emitido por el backend propio
- **THEN** `JwtValidator.validar()` lo acepta y devuelve un `AuthenticatedPrincipal` con los roles correctos

#### Scenario: Secreto ausente impide arranque
- **WHEN** `JWT_OWN_SECRET` no está definido en el entorno y `VITE_AUTH_PROVIDER=jwt`
- **THEN** la aplicación falla explícitamente al arrancar con error descriptivo, sin default inseguro

### Requirement: Validador multi-issuer — enrutamiento por iss + alg
El sistema SHALL validar tokens de múltiples issuers en un único punto de entrada. Para tokens con `alg=HS256` e `iss=JWT_OWN_ISSUER` SHALL verificar con el secreto propio. Para tokens con `alg=RS256` e `iss=KEYCLOAK_ISSUER` SHALL verificar con el JWKS cacheado existente (comportamiento C-06 sin cambio). Cualquier otra combinación `iss`/`alg` SHALL ser rechazada con 401.

#### Scenario: Token propio HS256 aceptado
- **WHEN** llega un request con JWT firmado HS256 por el backend (iss = JWT_OWN_ISSUER)
- **THEN** se valida correctamente sin round-trip a Keycloak

#### Scenario: Token Keycloak RS256 aceptado
- **WHEN** llega un request con JWT firmado RS256 por Keycloak (iss = KEYCLOAK_ISSUER)
- **THEN** se valida correctamente contra el JWKS cacheado (comportamiento C-06 conservado)

#### Scenario: Token con issuer desconocido rechazado
- **WHEN** llega un request con JWT cuyo `iss` no corresponde ni al issuer propio ni a Keycloak
- **THEN** el sistema rechaza el request con 401 sin exponer información sobre los issuers configurados

#### Scenario: Token con alg incorrecto para el issuer rechazado
- **WHEN** llega un token con `iss=JWT_OWN_ISSUER` pero firmado con RS256 (o viceversa)
- **THEN** el sistema rechaza el request con 401

### Requirement: TokenPolicy acepta lista de issuers configurados
`TokenPolicy` SHALL aceptar un `frozenset[str]` de issuers válidos (`issuers_aceptados`) en lugar de un único `issuer: str`. La validación de `iss` en `principal_desde_claims()` SHALL aceptar cualquier valor dentro del set. El `JWT_AUDIENCE` SHALL ser único para todos los providers.

#### Scenario: Claims con issuer propio aceptados por TokenPolicy
- **WHEN** `principal_desde_claims()` recibe claims con `iss = JWT_OWN_ISSUER`
- **THEN** devuelve un `AuthenticatedPrincipal` válido sin error de issuer

#### Scenario: Claims con issuer Keycloak aceptados por TokenPolicy
- **WHEN** `principal_desde_claims()` recibe claims con `iss = KEYCLOAK_ISSUER`
- **THEN** devuelve un `AuthenticatedPrincipal` válido (comportamiento C-06 conservado)

### Requirement: Refresh token persistente en DB para provider propio
El sistema SHALL implementar `DbRefreshTokenStore` (implementación de `RefreshTokenStore`) que persiste tokens en la tabla `refresh_tokens` (campos: `jti`, `usuario_id`, `expires_at`, `rotado_en`). La rotación SHALL marcar `rotado_en = now()` en el token viejo y emitir uno nuevo. Un token ya rotado o expirado SHALL ser rechazado con 401. TTL configurable (`refresh_token_ttl_seconds`, default 7 días).

#### Scenario: Refresh rota el token y persiste en DB
- **WHEN** `POST /api/v1/auth/refresh` recibe un refresh token vigente
- **THEN** el token viejo queda marcado como rotado en `refresh_tokens`, se emite un nuevo par (access + refresh), y el nuevo refresh queda registrado en DB

#### Scenario: Refresh ya rotado rechazado con 401
- **WHEN** `POST /api/v1/auth/refresh` recibe un refresh token ya rotado
- **THEN** responde 401 sin emitir tokens nuevos

#### Scenario: Refresh expirado rechazado con 401
- **WHEN** `POST /api/v1/auth/refresh` recibe un refresh token con `expires_at` en el pasado
- **THEN** responde 401 sin emitir tokens nuevos

