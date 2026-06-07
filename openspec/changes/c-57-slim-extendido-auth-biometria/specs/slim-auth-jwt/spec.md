## ADDED Requirements

### Requirement: SlimSettings incluye configuración de auth JWT

`SlimSettings` SHALL incluir los campos `jwt_own_secret` (str, obligatorio), `jwt_own_issuer` (str, default `activeexam-auth`), `jwt_audience` (str, default `activeexam`), `access_token_ttl_seconds` (int, default 900), `refresh_token_ttl_seconds` (int, default 604800), `auth_provider` (str, default `jwt`). Si `jwt_own_secret` o `embedding_encryption_key` faltan al arrancar, el proceso SHALL fallar con error explícito (sin default inseguro).

#### Scenario: arranque sin JWT_OWN_SECRET
- **WHEN** el proceso slim arranca sin la variable de entorno `JWT_OWN_SECRET`
- **THEN** Pydantic lanza `ValidationError` y el proceso termina con código no-cero

#### Scenario: arranque con todas las vars requeridas
- **WHEN** el proceso slim arranca con `DATABASE_URL`, `FRONTEND_ORIGIN`, `JWT_OWN_SECRET` y `EMBEDDING_ENCRYPTION_KEY`
- **THEN** la app levanta correctamente y `/api/v1/proctoring/docs` responde 200

### Requirement: slim_wiring construye JwtValidator HS256-only

El módulo `infrastructure/auth/slim_wiring.py` SHALL exponer `build_slim_jwt_validator(settings: SlimSettings) -> JwtValidator` que construye un `JwtValidator` capaz de validar tokens HS256 firmados con `jwt_own_secret`, sin fetchear JWKS ni requerir `keycloak_jwks_url`.

#### Scenario: token HS256 válido es aceptado
- **WHEN** se presenta un Bearer token HS256 firmado con `jwt_own_secret` y `iss=jwt_own_issuer`
- **THEN** `get_current_principal` retorna un `AuthenticatedPrincipal` válido

#### Scenario: token con secreto incorrecto es rechazado
- **WHEN** se presenta un Bearer token HS256 firmado con un secreto distinto
- **THEN** la dependencia lanza `HTTPException` 401

### Requirement: main_slim monta auth_router y cablea el state

`main_slim.py` SHALL incluir en el lifespan: `app.state.settings` (SlimSettings), `app.state.jwt_validator` (resultado de `build_slim_jwt_validator`), `app.state.session_factory` (slim session factory), `app.state.refresh_store` (DbRefreshTokenStore usando la session_factory). SHALL montar `auth_router` en `/api/v1/auth`.

#### Scenario: POST /api/v1/auth/login con credenciales válidas
- **WHEN** se hace `POST /api/v1/auth/login` con `username` y `password` correctos de un usuario existente en la tabla `usuario`
- **THEN** la respuesta es 200 con `access_token` (JWT HS256) y `refresh_token` (jti opaco)

#### Scenario: POST /api/v1/auth/login con credenciales inválidas
- **WHEN** se hace `POST /api/v1/auth/login` con password incorrecto
- **THEN** la respuesta es 401 con mensaje genérico (no revela si el usuario existe)

#### Scenario: GET /api/v1/auth/me con Bearer válido
- **WHEN** se hace `GET /api/v1/auth/me` con el access_token obtenido en login
- **THEN** la respuesta es 200 con el perfil del usuario (id_institucional, email, roles)

#### Scenario: POST /api/v1/auth/refresh rota el refresh token
- **WHEN** se hace `POST /api/v1/auth/refresh` con un `refresh_token` válido y no rotado
- **THEN** la respuesta es 200 con un nuevo `access_token` y nuevo `refresh_token`; el token anterior queda invalidado (rotado_en NOT NULL)
