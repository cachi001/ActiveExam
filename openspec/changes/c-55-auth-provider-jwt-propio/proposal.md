## Why

El proveedor de identidad Keycloak no levanta en el entorno de hosting actual por restricciones de RAM, bloqueando toda autenticación real. En lugar de reemplazar Keycloak (que es diferencial de venta como SSO institucional), se introduce una **abstracción `AuthProvider`** que convierte a Keycloak en un adapter opt-in conservado junto a un nuevo adapter JWT propio como default — sin romper el ADR-0009 ni el contrato de C-06.

## What Changes

- **Backend — nuevo endpoint `POST /api/v1/auth/login`**: recibe `email`/`username` + `password`, emite access token JWT propio (HS256, firmado con secreto backend) + refresh token persistente en DB.
- **Backend — campo `password_hash`** en `UsuarioModel`: migración Alembic en dos pasos (ADD nullable → backfill → SET NOT NULL para filas con auth local).
- **Backend — emisor JWT propio**: tokens con el mismo shape de claims que Keycloak (`sub`, `preferred_username`, `email`, `realm_access.roles`, `iss`, `aud`, `exp`, `iat`) para que `TokenPolicy.principal_desde_claims()` funcione sin cambios.
- **Backend — validador multi-issuer**: `JwtValidator` enruta por `iss` + `alg` — tokens propios (HS256, issuer `JWT_OWN_ISSUER`) verificados con secreto; tokens Keycloak (RS256, issuer `KEYCLOAK_ISSUER`) verificados con JWKS existente.
- **Backend — refresh token persistente**: `DbRefreshTokenStore` implementa `RefreshTokenStore` (puerto ya existente de C-06) sobre tabla `refresh_tokens` en Postgres; reemplaza `InMemoryRefreshTokenStore` para el provider propio.
- **Backend — seed / endpoint protegido de creación de usuario**: mínimo para que el login funcione; gestión completa de usuarios es otro change.
- **Frontend — interfaz `AuthProvider`**: puerto con adapters `jwt` (form login → `POST /auth/login`), `keycloak` (envuelve el actual), `demo`; selección por `VITE_AUTH_PROVIDER`.
- **Frontend — UI de login con formulario**: reemplaza el redirect-only actual cuando `VITE_AUTH_PROVIDER=jwt`.
- **Frontend — `getToken()` y `realFetch()`**: toman el token del provider activo, no hardcodeado a Keycloak.
- **Frontend — `authStore`**: se desacopla de Keycloak directamente; depende de la interfaz `AuthProvider`.

### Lo que NO cambia / NO entra en scope
- Keycloak **no se borra**: su adapter se conserva íntegro; `VITE_AUTH_PROVIDER=keycloak` reactiva el flujo actual.
- `TokenPolicy.principal_desde_claims()` **no cambia**: sigue siendo pura, agnóstica del emisor.
- La gestión/CRUD completo de usuarios (página de usuarios, alta masiva, etc.) es el **change siguiente**.
- MFA: el provider JWT propio emite `mfa_satisfecho: false` para roles que lo requieren (proctor, admin); en MVP se acepta con warning; MFA propio es un change futuro.

## Capabilities

### New Capabilities

- `jwt-own-issuer`: emisión, firma y validación de tokens JWT propios (HS256, multi-issuer) con refresh persistente en DB.
- `auth-provider-abstraction`: interfaz `AuthProvider` frontend (port + adapters jwt / keycloak / demo) con selección por env; formulario de login propio.
- `user-local-auth`: campo `password_hash` en `UsuarioModel`, hashing bcrypt/argon2, endpoint de login y creación mínima de usuarios con password.

### Modified Capabilities

- `jwt-validation-refresh` (spec de C-06): el validador acepta múltiples issuers/algoritmos (multi-issuer). El `RefreshTokenStore` tiene implementación DB para el provider propio. El contrato del puerto no cambia — solo se agrega un adapter concreto.

## Impact

- **Backend — archivos modificados**: `config.py` (nuevas vars), `wiring.py` (multi-issuer), `jwt_validator.py` (enrutamiento por iss/alg), `main.py` (wiring del store DB), `router.py` (nuevo `POST /auth/login`).
- **Backend — archivos nuevos**: `infrastructure/auth/own_issuer.py` (emisión HS256), `infrastructure/auth/db_refresh_store.py` (store persistente), `infrastructure/persistence/models/transactional.py` (campo `password_hash`, tabla `refresh_tokens`), migración Alembic en dos pasos.
- **Frontend — archivos nuevos**: `lib/auth/provider.ts` (interfaz), `lib/auth/adapters/jwt.ts`, `lib/auth/adapters/keycloak.ts` (wrapper), `lib/auth/adapters/demo.ts`, `screens/Login.tsx` (formulario), `lib/authProvider.ts` (singleton por env).
- **Frontend — archivos modificados**: `lib/authStore.ts`, `lib/api.ts` (`getToken()`, `realFetch()`), `lib/auth/keycloak.ts` (sin cambios de lógica — se envuelve), `main.tsx` (init del provider activo).
- **Dependencias backend nuevas**: `passlib[bcrypt]` (o `argon2-cffi`), `python-jose` o `PyJWT` ya existente para HS256.
- **Sin impacto** en la cadena de custodia, heartbeats, biometría ni ningún otro dominio.
