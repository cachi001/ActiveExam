# Spec — jwt-validation-refresh (delta — C-55)

> Delta sobre la spec de C-06 (`jwt-validation-refresh`). Extiende la validación JWT para soportar múltiples issuers y el refresh token persistente para el provider propio. Los requisitos originales de C-06 se conservan sin cambio.

## MODIFIED Requirements

### Requirement: Validación local de JWT contra JWKS cacheado
El sistema SHALL validar el JWT **localmente** contra la fuente correcta según el issuer: para `iss = JWT_OWN_ISSUER` SHALL verificar con HMAC-SHA256 y el secreto `JWT_OWN_SECRET`; para `iss = KEYCLOAK_ISSUER` SHALL verificar contra el JWKS cacheado de Keycloak (`KEYCLOAK_JWKS_URL`). En ambos casos la verificación es local (sin introspección remota por request). El campo `JWT_AUDIENCE` es compartido para ambos providers (`08` §Seguridad).

#### Scenario: Token propio HS256 validado localmente sin round-trip
- **WHEN** llega un request con JWT HS256 firmado por el backend propio (iss = JWT_OWN_ISSUER)
- **THEN** se valida localmente contra el secreto cacheado y el request procede, sin llamar a Keycloak ni a ningún servicio externo

#### Scenario: Token Keycloak RS256 validado localmente sin round-trip
- **WHEN** llega un request con JWT RS256 firmado por Keycloak (iss = KEYCLOAK_ISSUER)
- **THEN** se valida localmente contra el JWKS cacheado y el request procede, sin llamar a Keycloak por introspección

#### Scenario: Token inválido o expirado rechazado
- **WHEN** llega un request con JWT con firma inválida, expirado o con audiencia incorrecta
- **THEN** el sistema rechaza el request (401), sin exponer el recurso protegido

#### Scenario: Issuer desconocido rechazado con 401
- **WHEN** llega un request con JWT cuyo `iss` no corresponde a ningún issuer configurado
- **THEN** el sistema rechaza el request (401) con mensaje genérico

### Requirement: Access tokens cortos y refresh rotativo
El sistema SHALL emitir/aceptar access tokens de vida corta (15–60 min) y SHALL soportar **refresh rotativo** vía `POST /api/v1/auth/refresh`, invalidando el refresh token usado al rotarlo. Para el provider propio, el refresh SHALL persistirse en la tabla `refresh_tokens` en Postgres (`DbRefreshTokenStore`). Para el flujo Keycloak, el refresh sigue delegándose al IdP (sin cambio).

#### Scenario: Refresh propio rota el token y persiste en DB
- **WHEN** un cliente con un access token propio expirado invoca `POST /api/v1/auth/refresh` con su refresh token
- **THEN** recibe un nuevo access token JWT propio y un nuevo refresh token, quedando el refresh token anterior marcado como rotado en `refresh_tokens`

#### Scenario: Refresh inválido rechazado con 401
- **WHEN** se invoca `POST /api/v1/auth/refresh` con un refresh token ya rotado, expirado o inválido
- **THEN** el sistema rechaza la solicitud (401) y no emite nuevos tokens

#### Scenario: Refresh Keycloak conservado sin cambio
- **WHEN** el frontend usa el adapter Keycloak y el access token expira
- **THEN** el refresh se delega a Keycloak via el grant `refresh_token`, sin pasar por `DbRefreshTokenStore` (comportamiento C-06 conservado)
