# Spec — jwt-validation-refresh

> Capacidad de **validación local de JWT y refresh rotativo**. Valida el token contra el JWKS cacheado (sin round-trip por request); access 15–60 min; refresh rotativo vía `/api/v1/auth/refresh` (`08` §Seguridad). Su Done es: el JWT se valida localmente y el refresh rota.

## ADDED Requirements

### Requirement: Validación local de JWT contra JWKS cacheado
El sistema SHALL validar el JWT **localmente** contra el JWKS cacheado de Keycloak (`KEYCLOAK_JWKS_URL`), verificando firma, expiración y `JWT_AUDIENCE`, sin introspección remota por request (`08` §Seguridad).

#### Scenario: Token válido aceptado sin round-trip
- **WHEN** llega un request con un JWT firmado por Keycloak, no expirado y con la audiencia esperada
- **THEN** se valida localmente contra el JWKS cacheado y el request procede, sin llamar a Keycloak

#### Scenario: Token inválido o expirado rechazado
- **WHEN** llega un request con un JWT con firma inválida, expirado o con audiencia incorrecta
- **THEN** el sistema rechaza el request (401), sin exponer el recurso protegido

### Requirement: Access tokens cortos y refresh rotativo
El sistema SHALL emitir/aceptar access tokens de vida corta (15–60 min) y SHALL soportar **refresh rotativo** vía `POST /api/v1/auth/refresh`, invalidando el refresh token usado al rotarlo (`08` §Seguridad, `03` §Rutas públicas).

#### Scenario: Refresh rota el token
- **WHEN** un cliente con un access token expirado invoca `POST /api/v1/auth/refresh` con su refresh token
- **THEN** recibe un nuevo access token y un nuevo refresh token, quedando el refresh token anterior invalidado (rotación)

#### Scenario: Refresh inválido rechazado
- **WHEN** se invoca `POST /api/v1/auth/refresh` con un refresh token ya rotado o inválido
- **THEN** el sistema rechaza la solicitud y no emite nuevos tokens
