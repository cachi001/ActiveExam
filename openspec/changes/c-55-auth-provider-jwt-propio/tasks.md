## 1. Infraestructura backend — dependencias y config

- [x] 1.1 Agregar `passlib[bcrypt]` al `pyproject.toml` / `requirements.txt` del backend
- [x] 1.2 Agregar las nuevas variables de entorno a `Settings` en `backend/app/config.py`: `jwt_own_secret` (str, sensible), `jwt_own_issuer` (str), `refresh_token_ttl_seconds` (int, default 604800), `auth_provider` (Literal["jwt", "keycloak"], default "jwt")
- [x] 1.3 Actualizar `.env.example` / `docker-compose.yml` con los nuevos env vars (sin valores reales — solo keys con comentario descriptivo)

## 2. Migración Alembic — dos pasos

- [x] 2.1 Generar y escribir migración Alembic **paso 1** (no destructiva): `ADD COLUMN password_hash TEXT` (nullable) y `ADD COLUMN auth_provider TEXT DEFAULT 'keycloak'` en tabla `usuarios`
- [x] 2.2 En la misma migración paso 1: `CREATE TABLE refresh_tokens (id UUID PK, jti TEXT UNIQUE NOT NULL, usuario_id UUID FK → usuarios(id) ON DELETE CASCADE, expires_at TIMESTAMPTZ NOT NULL, rotado_en TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now())`
- [x] 2.3 Crear índices en `refresh_tokens`: `UNIQUE(jti)` y `INDEX(usuario_id)`, `INDEX(expires_at)` para cleanup eficiente
- [x] 2.4 Documentar en comentario de la migración que el paso 2 (NOT NULL) no aplica en este change — usuarios Keycloak no tienen password local

## 3. Modelo y dominio backend

- [x] 3.1 Agregar campos `password_hash: str | None = None` y `auth_provider: str = "keycloak"` a `UsuarioModel` en `backend/app/infrastructure/persistence/models/transactional.py`
- [x] 3.2 Crear `backend/app/infrastructure/auth/own_issuer.py`: función `emitir_jwt_propio(usuario, settings) -> str` que firma HS256 con los claims requeridos (sub, preferred_username, email, realm_access.roles, iss, aud, exp, iat). Usar PyJWT (ya en el proyecto)
- [x] 3.3 Crear `backend/app/infrastructure/auth/hashing.py`: `hashear_password(plain: str) -> str` y `verificar_password(plain: str, hashed: str) -> bool` usando passlib bcrypt 12 rounds
- [x] 3.4 Crear `backend/app/infrastructure/auth/db_refresh_store.py`: clase `DbRefreshTokenStore(RefreshTokenStore)` con métodos `issue(usuario_id)`, `is_valid(jti)`, `rotate(old_jti)` usando SQLAlchemy async sobre tabla `refresh_tokens`. Debe manejar expiración por `expires_at`
- [x] 3.5 Modificar `TokenPolicy` en `backend/app/domain/auth/token.py`: cambiar `issuer: str` por `issuers_aceptados: frozenset[str]`; actualizar `_verificar_issuer()` para aceptar cualquier issuer del set. Mantener retrocompatibilidad con `KEYCLOAK_ISSUER`

## 4. Validador multi-issuer

- [x] 4.1 Agregar función de verificación HS256 en `backend/app/infrastructure/auth/verifiers.py`: `build_hs256_verify(secret: str) -> VerifyFn` que valida con PyJWT (algoritmo=HS256, verify_signature=True)
- [x] 4.2 Modificar `JwtValidator.validar()` en `backend/app/infrastructure/auth/jwt_validator.py`: leer `alg` del header y `iss` del payload no verificado; despachar a `verify_fn_hs256` (issuer propio) o `verify_fn_rs256` (Keycloak); rechazar combinaciones no reconocidas con `UnauthenticatedError`
- [x] 4.3 Actualizar `build_jwt_validator(settings)` en `backend/app/infrastructure/auth/wiring.py`: construir dos `verify_fn` (HS256 y RS256) y el `JwtValidator` multi-issuer con ambas; pasar `issuers_aceptados` a `TokenPolicy`

## 5. Endpoints de auth backend

- [x] 5.1 Crear schemas `LoginRequest` y `LoginResponse` en `backend/app/presentation/api/v1/auth/router.py` con `model_config = ConfigDict(extra='forbid')`
- [x] 5.2 Implementar `POST /api/v1/auth/login` en el router de auth: buscar usuario por email O id_institucional, verificar `password_hash` con bcrypt, emitir JWT propio, persistir refresh en DB, responder 200. Responder 401 con mensaje genérico en todos los casos de fallo (timing-safe)
- [x] 5.3 Actualizar `POST /api/v1/auth/refresh` para usar `DbRefreshTokenStore` cuando el provider es `jwt` (el store se inyecta vía `app.state.refresh_store` — cambiar el tipo al concreto en main.py)
- [x] 5.4 Registrar la ruta `POST /auth/login` como pública (sin `get_current_principal`) en el router

## 6. Endpoint de creación de usuario (mínimo)

- [x] 6.1 Crear `backend/app/presentation/api/v1/users/router.py` con `POST /` protegido por `require_roles([Rol.admin_sistema])`
- [x] 6.2 Crear schemas `CrearUsuarioRequest` y `UsuarioResponse` con `model_config = ConfigDict(extra='forbid')`. Validar `len(password) >= 8`
- [x] 6.3 Implementar lógica: hashear password, crear `UsuarioModel` con `auth_provider='local'`, manejar IntegrityError → 409 Conflict si email o id_institucional ya existen
- [x] 6.4 Registrar el router de users en `backend/app/main.py` bajo `/api/v1/users`

## 7. Seed de usuarios de prueba

- [x] 7.1 Crear `backend/scripts/seed_users.py`: lee `SEED_ESTUDIANTE_PASSWORD`, `SEED_PROCTOR_PASSWORD`, `SEED_ADMIN_PASSWORD` del entorno; crea 3 usuarios demo con bcrypt; falla si `ENVIRONMENT=production`; es idempotente (verifica existencia antes de insertar)
- [x] 7.2 Documentar el script en el `README` del backend con instrucciones de uso local

## 8. Frontend — interfaz AuthProvider y adapters

- [x] 8.1 Crear `frontend/src/lib/auth/provider.ts` con la interfaz `AuthProvider` (métodos: `init`, `login`, `logout`, `getToken`, `getPrincipal`, `onAuthChange`)
- [x] 8.2 Crear `frontend/src/lib/auth/adapters/jwt.ts` (`JwtAdapter`): `login()` llama `POST /api/v1/auth/login`, guarda `access_token` en `sessionStorage['jwt_access_token']` con `expires_at`; `getToken()` retorna token si vigente o refresca automáticamente; `logout()` limpia sessionStorage
- [x] 8.3 Crear `frontend/src/lib/auth/adapters/keycloak.ts` (`KeycloakAdapter`): wrapper sobre `lib/auth/keycloak.ts` sin modificar la lógica interna; implementa la interfaz `AuthProvider`
- [x] 8.4 Crear `frontend/src/lib/auth/adapters/demo.ts` (`DemoAdapter`): porta el comportamiento actual del selector de roles demo; sin red; `getToken()` retorna `'demo'`
- [x] 8.5 Crear `frontend/src/lib/authProvider.ts`: singleton que lee `VITE_AUTH_PROVIDER` y exporta el adapter correcto (default: `jwt`)

## 9. Frontend — authStore y api desacoplados

- [x] 9.1 Modificar `frontend/src/lib/authStore.ts`: eliminar imports directos de `keycloak.ts`; reemplazar `hydrateFromKeycloak` por `hydrateFromProvider(provider: AuthProvider)`; `login()` y `logout()` delegan al provider activo; `loginDemo` pasa por `DemoAdapter`
- [x] 9.2 Modificar `frontend/src/lib/api.ts`: cambiar `import { getToken } from './auth/keycloak'` por `import { authProvider } from './authProvider'`; `realFetch` usa `authProvider.getToken()`
- [x] 9.3 Modificar `frontend/src/main.tsx`: reemplazar init de Keycloak por `authProvider.init()` + `authProvider.onAuthChange(...)` + `useAuth.getState().hydrateFromProvider(authProvider)`

## 10. Frontend — pantalla de login

- [x] 10.1 Crear `frontend/src/screens/Login.tsx` con formulario usuario/contraseña: campos `emailOUsername` y `password`, botón submit con loading, mensaje de error inline. Solo se renderiza cuando el provider es `JwtAdapter` y `status === 'unauthenticated'`
- [x] 10.2 Conectar `Login.tsx` al router de la app (hash-based): ruta `#/login` muestra la pantalla; redirect automático a `#/login` cuando `status === 'unauthenticated'` y el provider es `jwt`
- [x] 10.3 Añadir warning visible en el dashboard de `proctor` y `admin_sistema` cuando `!principal.mfa_satisfecho` informando que MFA no está activo en el provider propio (sin bloquear el acceso en MVP)

## 11. Tests backend — sin mocks de DB (testcontainers / DB efímera)

- [x] 11.1 Test de integración `test_login_endpoint.py`: verifica login exitoso, password incorrecto (401 mismo mensaje), usuario sin password_hash (401), timing constante (mismo mensaje en todos los casos de fallo)
- [x] 11.2 Test de `DbRefreshTokenStore`: issue → is_valid → rotate → reuso detectado (401). Usa DB efímera (testcontainers o SQLite en modo async con el mismo esquema). Verifica que el token rotado queda con `rotado_en != NULL`
- [x] 11.3 Test de `JwtValidator` multi-issuer: token HS256 propio aceptado, token RS256 Keycloak aceptado (con JWKS mock inyectado), issuer desconocido rechazado, alg incorrecto para issuer rechazado
- [x] 11.4 Test de `TokenPolicy` con `issuers_aceptados`: verifica que acepta tanto el issuer propio como el de Keycloak, y rechaza un issuer no configurado
- [x] 11.5 Test del endpoint `POST /api/v1/users/`: creación exitosa por admin_sistema, rechazo por rol incorrecto (403), email duplicado (409), password < 8 chars (422)
- [x] 11.6 Test del script seed: verifica idempotencia (no duplica) y que falla en producción

## 12. Tests frontend

- [x] 12.1 Test unitario de `JwtAdapter`: mock de `fetch` para `POST /auth/login`; verifica que el token se guarda en sessionStorage, que `getToken()` lo retorna mientras vigente, que llama refresh cuando está por expirar, que logout limpia sessionStorage
- [x] 12.2 Test de `KeycloakAdapter`: verifica que delega correctamente a `keycloak.ts` y que no hay regresiones en el comportamiento de Keycloak (puede usar el stub existente de keycloak-js)
- [x] 12.3 Test de `authStore` con `JwtAdapter` mockeado: `hydrateFromProvider` pone `status='authenticated'` cuando el adapter tiene sesión; `logout()` pone `status='unauthenticated'`
- [x] 12.4 Test de `Login.tsx`: renderiza formulario cuando status=unauthenticated con adapter jwt; submit en loading bloquea campos; error se muestra con 401; redirige en login exitoso

## 13. Documentación y variables de entorno

- [x] 13.1 Actualizar `backend/app/config.py` con docstring explicando el modelo multi-provider y qué vars son requeridas para cada modo
- [x] 13.2 Actualizar `.env.example` con todos los valores nuevos agrupados bajo `# Auth provider propio (C-55)` con comentario sobre cuáles son sensibles (Vault)
- [x] 13.3 Documentar en el `README` del proyecto (o en `docs/auth-providers.md`) cómo cambiar entre providers (`VITE_AUTH_PROVIDER=jwt|keycloak|demo`) y cómo correr el seed en desarrollo
- [x] 13.4 Documentar las open questions del design.md resueltas (issuer URI, TTL refresh, algoritmo bcrypt) antes de cerrar el change
