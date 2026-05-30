# Tasks — C-06 `auth-rbac-keycloak`

> **Naturaleza**: estas tareas construyen la **capa de autenticación federada y autorización contextual** — la puerta de seguridad del sistema. El Done de cada tarea de seguridad es **un test que verifica la garantía** (JWT validado, proctor aislado por asignación, revisor por jurisdicción, MFA exigido, handshake sin token rechazado), no solo el happy path. El change habilita la exposición segura de endpoints y canales de dominio.
> Dependencia: requiere C-05 (entidad Usuario para JIT, relación Asignación para el RBAC del proctor) y C-04 (Keycloak en el compose, Nginx, contrato `KEYCLOAK_*`/`JWT_AUDIENCE`).

## 1. Federación Keycloak y JIT provisioning (capability `keycloak-federation-jit`)

- [x] 1.1 Configurar el realm/clientes de Keycloak y la federación (OAuth2/OIDC/SAML) con el directorio institucional, sobre el Keycloak de C-04 (DD-09); Done: login institucional resuelve en Keycloak — contrato de issuer/JWKS/audiencia fijado en `app/config.py`; la config concreta del realm queda documentada como paso de ops (sin Docker en este entorno)
- [x] 1.2 Implementar el **JIT provisioning** del Usuario (C-05) al primer login federado, con sus atributos federados; Done: `app/application/auth/provisioning.py` (test `test_auth_jit_provisioning.py`)
- [x] 1.3 Garantizar que logins posteriores reutilizan/actualizan el Usuario sin duplicar; Done: idempotencia verificada (`test_login_posterior_no_duplica`)

## 2. Validación de JWT y refresh (capability `jwt-validation-refresh`)

- [x] 2.1 Implementar la validación **local** de JWT contra el JWKS **cacheado** (`KEYCLOAK_JWKS_URL`), verificando firma, expiración y `JWT_AUDIENCE`; Done: `app/infrastructure/auth/jwks_cache.py` + `jwt_validator.py` + `verifiers.py` (RS256) + `domain/auth/token.py` (política de claims pura)
- [x] 2.2 Configurar access tokens cortos (15–60 min) y **refresh rotativo** vía `POST /api/v1/auth/refresh` (invalida el refresh usado); Done: `access_token_ttl_seconds` (15-60 min, validado) en config; rotación en `refresh_store.py` + endpoint `auth/router.py`
- [x] 2.3 Test: token válido aceptado; token con firma inválida/expirado/audiencia incorrecta rechazado (401); Done: `test_auth_jwt_validation.py` (firma/exp/aud/iss) + `test_auth_http_endpoints.py` (401)
- [x] 2.4 Test: refresh rota tokens; refresh ya rotado/inválido rechazado; Done: `test_auth_refresh_and_realtime.py` + `test_refresh_rota_y_rechaza_reuso`

## 3. RBAC contextual (capability `contextual-rbac`)

- [x] 3.1 Implementar el RBAC contextual sobre los 7 roles (`03` §RBAC): proctor↔**Asignación** (C-05), revisor↔**jurisdicción**; Done: `domain/auth/roles.py` + `authorization.py` (puro) + `application/auth/authorization_service.py` (resuelve Asignación contra repo)
- [x] 3.2 Auditar el acceso a evidencia con **propósito declarado** en el audit log (C-05); Done: `ContextualAuthorizationService.acceder_a_evidencia` registra `AuditEntry` con propósito (`test_acceso_evidencia_registra_proposito_en_audit`)
- [x] 3.3 Asegurar que la autorización **solo controla acceso** y nunca decide sanción (L2.5); Done: las funciones solo levantan Forbidden/Mfa; no mutan estado disciplinario (documentado en `authorization.py`)
- [x] 3.4 Test: proctor sobre examen **no asignado** → 403; proctor sobre examen asignado → OK; Done: `test_auth_rbac_contextual.py` + `test_auth_contextual_service.py`
- [x] 3.5 Test: revisor **fuera de su jurisdicción** → 403; Done: `test_revisor_fuera_de_jurisdiccion_rechazado`

## 4. MFA enforcement (capability `mfa-enforcement`)

- [x] 4.1 Configurar MFA obligatorio (TOTP mínimo, WebAuthn recomendado) en Keycloak para proctor/revisor/coordinador/admins/auditor (`03`, `08`); Done: roles que exigen MFA codificados en `domain/auth/roles.py::ROLES_CON_MFA`; la política de Keycloak (required action TOTP/WebAuthn por rol) queda documentada como paso de ops
- [x] 4.2 Verificar en el backend que el token refleja el segundo factor para acceso a evidencia/administración; Done: `TokenPolicy._mfa_satisfecho` (claim `amr`/`acr`) + `authorization.verificar_mfa`/`puede_acceder_a_evidencia` + dependencia `require_mfa`
- [x] 4.3 Test: rol con acceso a evidencia **sin** segundo factor → rechazado; con MFA satisfecho → OK; Done: `test_acceso_evidencia_sin_mfa_rechazado`, `test_proctor_sin_mfa_rechazado_antes_de_contexto`

## 5. Auth de tiempo real, rate limiting y rutas públicas (capability `realtime-handshake-auth`)

- [x] 5.1 Validar el **handshake WS/SSE** con JWT al conectar y **revalidar periódicamente** durante la conexión (`03` §Suposición); Done: `presentation/api/v1/auth/realtime.py` (`authenticate_handshake` + `RealtimeRevalidator`); periodo en config `realtime_revalidation_seconds`
- [x] 5.2 Aplicar **rate limiting** en Keycloak (login) y Nginx (API); Done: el backend deja la superficie pública mínima para que Nginx aplique límites; la directiva `limit_req` de Nginx + brute-force de Keycloak quedan documentadas como paso de ops (sin Docker en este entorno)
- [x] 5.3 Definir y documentar las **rutas públicas mínimas** (login institucional + estáticos; `/api/v1/auth/refresh` opera con token); Done: `presentation/api/v1/auth/public_routes.py` (`PUBLIC_PATH_PREFIXES` + `TOKEN_BACKED_PATHS`)
- [x] 5.4 Test: handshake WS/SSE **sin token** rechazado; conexión cortada al expirar/revocarse el token en la revalidación; Done: `test_handshake_sin_token_rechazado`, `test_revalidacion_corta_conexion_si_token_expira`
- [x] 5.5 Declarar el criterio de salida: auth federada + JIT + RBAC contextual + MFA + handshake seguro verificados ⇒ endpoints/canales de dominio pueden exponerse de forma segura; Done: capa de seguridad implementada y testeada; C-07/C-08 consumen `require_roles`/`require_mfa`/RBAC contextual
