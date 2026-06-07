## Context

El sistema usa Keycloak (ADR-0009) como único IdP. En el entorno de hosting actual, Keycloak no levanta por restricciones de RAM, dejando sin autenticación real a toda la plataforma. La infraestructura de validación de JWT de C-06 ya es agnóstica del emisor en la capa criptográfica — `JwtValidator` recibe un `verify_fn` inyectable — pero solo está cableado para RS256 + JWKS de Keycloak.

El objetivo no es reemplazar Keycloak (es diferencial de venta como SSO institucional) sino introducir una **abstracción `AuthProvider`** que permita operar sin él cuando no está disponible, manteniéndolo como adapter opt-in.

Constraints aplicables del proyecto:
- Pydantic `extra='forbid'` en todos los schemas.
- Migraciones Alembic destructivas en dos pasos.
- Secretos nunca hardcodeados (twelve-factor / Vault).
- Tests sin mocks de DB (testcontainers / DB efímera).
- No hay gestión de usuarios en este change: solo el mínimo para que login funcione.

## Goals / Non-Goals

**Goals:**
- Endpoint `POST /api/v1/auth/login` funcional (usuario + password → JWT propio + refresh persistente).
- Validador multi-issuer: acepta tokens propios (HS256) y Keycloak (RS256/JWKS) por configuración, sin que el resto del código lo note.
- Frontend con interfaz `AuthProvider` + adapter `jwt` (formulario login) + adapters `keycloak` y `demo` conservados.
- `getToken()` y `realFetch()` agnósticos del provider activo.
- Migración Alembic en dos pasos para `password_hash` y tabla `refresh_tokens`.
- Seed / endpoint protegido mínimo para crear usuarios con password.

**Non-Goals:**
- CRUD/gestión completa de usuarios (página de usuarios, alta masiva, baja, edición de roles) — es el change siguiente.
- MFA propio — el provider JWT emite `mfa_satisfecho: false` para roles que lo exigen; MFA propio es un change futuro independiente.
- Federation JIT / SAML / LDAP con el provider propio — sigue siendo responsabilidad de Keycloak cuando esté activo.
- Eliminar o deprecar Keycloak.

## Decisions

### D1 — Algoritmo JWT propio: HS256 con secreto del backend (MVP)

**Decisión**: usar **HMAC-SHA256 (HS256)** con un secreto rotable (`JWT_OWN_SECRET`, 256+ bits, vía env/Vault) para firmar los tokens propios.

**Alternativa considerada**: RS256 con par de claves propio + JWKS propio del backend.

**Por qué HS256 para MVP**:
- Single-issuer self-hosted: el backend que firma es el mismo que verifica — no hay tercero que necesite validar públicamente.
- Cero dependencias adicionales de infra (no hay que exponer un endpoint JWKS propio, no hay gestión de par de claves asimétrico).
- Rotación de secreto sencilla: cambiar `JWT_OWN_SECRET` invalida todos los tokens vigentes (comportamiento deseado en rotación de emergencia).
- PyJWT ya está en el proyecto para RS256 — soporta HS256 nativamente.

**Por qué RS256 propio es alternativa de escala**:
- Necesaria si se quiere validación distribuida sin compartir el secreto (múltiples servicios, terceros).
- Recomendada si el sistema crece a múltiples microservicios o si se expone un JWKS público.
- La abstracción del `verify_fn` en `JwtValidator` hace que la migración sea trivial (cambiar el adapter, no la arquitectura).

**Riesgo aceptado**: HS256 requiere que el secreto nunca se exponga. Con Vault + tmpfs efímero esto es manejable a la escala del MVP.

---

### D2 — Multi-issuer en `JwtValidator`: enrutamiento por `iss` + `alg`

**Decisión**: `JwtValidator.validar()` lee el header decodificado (`iss` del payload + `alg` del header) y despacha a la función de verificación correcta:

```
alg == "HS256" AND iss == JWT_OWN_ISSUER  →  verify_fn_hs256(secreto)
alg == "RS256" AND iss == KEYCLOAK_ISSUER →  verify_fn_rs256(jwks_cache)  [existente]
```

El campo `iss` se lee del payload **antes** de verificar la firma (igual que `kid` ya se lee del header antes de verificar). La firma verifica después, usando la clave correcta según el issuer.

`TokenPolicy` recibe una lista de issuers aceptados (`issuers_aceptados: frozenset[str]`) en lugar de un único `issuer: str`. La validación de issuer en `principal_desde_claims()` acepta cualquiera de la lista. `JWT_AUDIENCE` se mantiene único (mismo audience para ambos providers — simplifica la validación).

**Alternativa descartada**: dos instancias separadas de `JwtValidator` (una por provider) con un dispatcher externo. Más acoplamiento en el punto de entrada HTTP sin beneficio real.

---

### D3 — Shape de claims del JWT propio: compatible con `TokenPolicy` existente

Los tokens emitidos por el provider propio usan **exactamente el mismo shape** que Keycloak:

```json
{
  "sub": "<uuid-del-usuario>",
  "preferred_username": "<id_institucional>",
  "email": "<email>",
  "realm_access": { "roles": ["estudiante"] },
  "iss": "<JWT_OWN_ISSUER>",
  "aud": "<JWT_AUDIENCE>",
  "exp": <unix-timestamp>,
  "iat": <unix-timestamp>
}
```

`TokenPolicy.principal_desde_claims()` **no cambia**. Esto garantiza que toda la capa de autorización RBAC (C-06) funciona sin modificación.

`amr` no se incluye en el token propio (no hay MFA propio en este change), por lo que `mfa_satisfecho` será `false` para todos los roles. Roles que exigen MFA (`proctor`, `admin_sistema`) recibirán un warning en el frontend (no un bloqueo en este MVP — bloqueo MFA es change futuro).

---

### D4 — Refresh token persistente: `DbRefreshTokenStore`

El puerto `RefreshTokenStore` (C-06) ya define la interfaz `issue()` / `is_valid()` / `rotate()`. Se agrega una implementación `DbRefreshTokenStore` que persiste en la tabla `refresh_tokens`:

```
refresh_tokens(
  id          UUID PK DEFAULT gen_random_uuid(),
  jti         TEXT UNIQUE NOT NULL,        -- token opaco (secrets.token_urlsafe(32))
  usuario_id  UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  expires_at  TIMESTAMPTZ NOT NULL,
  rotado_en   TIMESTAMPTZ,                -- NULL = vigente, NOT NULL = ya rotado
  created_at  TIMESTAMPTZ DEFAULT now()
)
```

TTL configurable (`refresh_token_ttl_seconds`, default 7 días). La rotación marca `rotado_en = now()` en el registro viejo y crea uno nuevo. El cleanup de expirados corre como tarea Postgres (pg-boss o SKIP LOCKED) periódica.

`InMemoryRefreshTokenStore` se conserva para tests unitarios (sin DB). `DbRefreshTokenStore` es la implementación de producción para el provider propio. Keycloak sigue gestionando sus propios refresh (sin cambio).

---

### D5 — Migración Alembic en dos pasos para `password_hash`

**Regla del proyecto**: migraciones destructivas en dos pasos.

**Paso 1** (no destructivo — deployable sin downtime):
- `ALTER TABLE usuarios ADD COLUMN password_hash TEXT;` (nullable)
- `ALTER TABLE usuarios ADD COLUMN auth_provider TEXT DEFAULT 'keycloak';`

**Paso 2** (después de backfill — en este change solo hay usuarios institucionales sin password, así que el backfill es vacío):
- No se agrega `NOT NULL` porque usuarios federados Keycloak legítimamente no tienen password local. `password_hash IS NULL` significa "no tiene credencial local" (usa Keycloak/SAML).

Tabla `refresh_tokens` se crea en paso 1 (es nueva, no destructiva).

---

### D6 — Interfaz `AuthProvider` frontend: port + adapters

```typescript
interface AuthProvider {
  init(): Promise<void>;
  login(creds?: { email: string; password: string }): Promise<void>;
  logout(): Promise<void>;
  getToken(): string | undefined;
  getPrincipal(): Principal | null;
  onAuthChange(cb: (status: AuthStatus) => void): () => void; // unsubscribe
}
```

Selección por `VITE_AUTH_PROVIDER`:
- `jwt` → `JwtAdapter` (formulario, POST `/auth/login`, localStorage seguro)
- `keycloak` → `KeycloakAdapter` (envuelve el flujo PKCE existente sin cambios)
- `demo` → `DemoAdapter` (comportamiento actual del modo demo)

`authStore` (Zustand) deja de importar `keycloak.ts` directamente — consume el provider activo. `getToken()` en `api.ts` delega al provider activo.

---

### D7 — Storage del token propio en frontend

Access token: `sessionStorage` (más seguro que `localStorage` — se borra al cerrar pestaña, no persiste entre sesiones distintas). Si se requiere persistencia entre tabs del mismo origen, se puede usar `localStorage` con rotación corta de access token (15 min).

Refresh token: **no se persiste en el frontend en MVP**. El flujo es: al cerrar y reabrir el navegador, el usuario hace login de nuevo. Esto simplifica el modelo de seguridad (sin refresh token en storage que pueda ser robado). Se puede añadir persistencia del refresh en `httpOnly cookie` en un change futuro.

---

### D8 — Creación mínima de usuarios con password

**Endpoint protegido** `POST /api/v1/users/` (requiere rol `admin_sistema`): crea un usuario con `password_hash` (bcrypt, 12 rounds). El schema de request requiere `email`, `id_institucional`, `password`, `roles`.

**Seed de desarrollo**: script `backend/scripts/seed_users.py` que crea 3 usuarios demo (estudiante, proctor, admin) con passwords de entorno (`SEED_*_PASSWORD`). Solo corre en `environment != production`.

**Hash elegido: bcrypt** (`passlib[bcrypt]`). Argon2 es la alternativa recomendada modernamente, pero bcrypt tiene soporte más amplio y es suficiente para MVP. Se documenta como decisión revisable.

## Risks / Trade-offs

- **[Riesgo] HS256 con secreto compartido** → El secreto `JWT_OWN_SECRET` debe gestionarse con Vault + tmpfs. Si se filtra, todos los tokens activos son forjables. Mitigación: TTL de access token corto (15 min), rotación de secreto como runbook operacional documentado.

- **[Riesgo] `mfa_satisfecho: false` para proctor/admin** → Roles que exigen MFA (RN-AU-05) operarán sin MFA real en este change. Mitigación: documentar el gap en el DPIA, advertir en el frontend, priorizar el change de MFA propio post-MVP.

- **[Trade-off] `password_hash` nullable** → Usuarios Keycloak no tienen password local. La columna nullable modela correctamente el multi-provider, pero requiere que la lógica de login verifique `auth_provider` antes de comparar hash.

- **[Riesgo] Refresh sin httpOnly cookie** → El refresh en sessionStorage es accesible desde JS. Si hay XSS, el refresh puede extraerse. Mitigación: CSP estricto (ya implementado), access token corto (15 min), sin persistent refresh en MVP.

- **[Trade-off] Keycloak en estado "conservado pero sin test CI"** → El adapter Keycloak sigue existiendo pero CI no puede levantarlo. Mitigación: los tests del adapter Keycloak son de integración manuales (documentado); el contrato del puerto se testea con el adapter JWT + DB efímera.

## Migration Plan

1. **Rama de desarrollo**: crear branch `feat/c-55-auth-provider-jwt-propio`.
2. **Paso 1 de migración Alembic**: aplicar `ADD COLUMN password_hash`, `ADD COLUMN auth_provider`, `CREATE TABLE refresh_tokens`. Sin downtime.
3. **Seed local**: correr `seed_users.py` en entorno local/staging para tener usuarios de prueba.
4. **Deploy con `VITE_AUTH_PROVIDER=jwt`**: apagar el redirect a Keycloak, mostrar formulario.
5. **Rollback**: cambiar `VITE_AUTH_PROVIDER=keycloak` — el adapter Keycloak sigue intacto. Las columnas nuevas en DB son aditivas (no destructivas), el rollback no requiere migración inversa.
6. **Paso 2 de migración** (N/A en este change): no se agrega `NOT NULL` porque usuarios Keycloak no tienen password.

## Open Questions

> **Estado**: todas las preguntas fueron resueltas antes de implementar (C-55 implementado).

1. **¿`JWT_OWN_ISSUER` como URL o como string arbitrario?** — **RESUELTO**: se usa el string fijo `activeexam-auth` (no una URL). Razón: el dominio de hosting no está estabilizado; un string arbitrario no-URI es válido para uso interno. Si el dominio se estabiliza en producción, migrar a `https://<dominio>/auth` es un cambio de configuración (no de código).

2. **¿TTL del refresh token?** — **RESUELTO**: **7 días (604800 segundos)**. Renovable con cada uso por rotación. El usuario debe reloguearse si no usa la app en 7 días. Configurable vía `REFRESH_TOKEN_TTL_SECONDS`.

3. **¿bcrypt vs argon2?** — **RESUELTO**: **bcrypt 12 rounds** (`passlib[bcrypt]`). Suficiente para MVP. Argon2 se documenta como mejora recomendada para cuando se tenga más control sobre el entorno de ejecución (memoria garantizada). La abstracción en `hashing.py` facilita la migración.

4. **¿MFA propio como bloqueante o como warning en MVP?** — **RESUELTO**: **warning no bloqueante**. El token propio emite `mfa_satisfecho: false` (sin `amr`). El frontend muestra un banner visible en `StaffShell` para proctor/admin_sistema. El bloqueo real de acceso sin MFA queda como deuda técnica documentada en `StaffShell` y en `own_issuer.py`.
