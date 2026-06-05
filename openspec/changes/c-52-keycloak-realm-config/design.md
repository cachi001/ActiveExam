## Context

El stack actual levanta Keycloak 26.0.7 en modo `start-dev` sin ningún realm configurado. El backend (`token.py`) valida:

1. `iss == KEYCLOAK_ISSUER` (env var).
2. `aud ∋ JWT_AUDIENCE` (env var, default `proctoring-api`).
3. Roles desde `realm_access.roles` contra el enum `Rol`.
4. MFA desde claim `amr` — valores aceptados: `otp`, `totp`, `mfa`, `hwk`, `swk`, `webauthn`, `fido`, `u2f`.

**Problema del issuer en Docker**: Keycloak construye el claim `iss` con el hostname con que fue alcanzado. Si el browser llega a `http://localhost:8080` e `iss` queda `http://localhost:8080/realms/proctoring`, pero `KEYCLOAK_ISSUER=http://keycloak:8080/...`, el backend rechaza el token. La solución es fijar el hostname de emisión con `KC_HOSTNAME_URL=http://localhost:8080` para que `iss` sea siempre `http://localhost:8080/realms/proctoring`, y ajustar `KEYCLOAK_ISSUER` en `.env.example` al mismo valor. La JWKS URL sigue usando `keycloak:8080` (backchannel interno Docker) — el backend llama JWKS directo, no pasa por el browser.

## Goals / Non-Goals

**Goals**:
- Realm `proctoring` importado automáticamente al arrancar (`start-dev --import-realm`).
- Claim `aud` contiene `proctoring-api` en todo access token del client `proctoring-spa`.
- Claim `iss` es siempre `http://localhost:8080/realms/proctoring` (hostname fijo).
- 3 usuarios de prueba funcionales con password grant (sin browser) para desarrollo/tests.
- Cero código de aplicación tocado.

**Non-Goals**:
- Integración OIDC en el frontend (change posterior).
- MFA real/OTP para usuarios de prueba (ver sección de decisiones sobre MFA).
- Configuración de producción / HTTPS real / federación LDAP.
- Keycloak en alta disponibilidad.

## Decisions

### D1 — Import por volumen read-only (`--import-realm`)

Keycloak 26 soporta import declarativo al arrancar con `--import-realm` si existe `/opt/keycloak/data/import/*.json`. Se monta el realm JSON como volumen read-only. Alternativas descartadas:
- Script de bootstrap via Admin API (frágil, depende de timing de arranque, más complejidad).
- Realm exportado manualmente post-arranque (no reproducible; rompe infra-as-code).

### D2 — Hostname fijo con `KC_HOSTNAME_URL`

`KC_HOSTNAME_URL=http://localhost:8080` fuerza el `iss` a `http://localhost:8080/realms/proctoring` independientemente del hostname interno Docker. Esto permite que:
- `KEYCLOAK_ISSUER=http://localhost:8080/realms/proctoring` (iss del token).
- `KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs` (backchannel interno).

Esta asimetría es INTENCIONAL: el browser obtiene el token en localhost, el backend valida JWKS por la red Docker interna (más eficiente, sin salir).

### D3 — Roles en realm-level (no client-level)

Los roles `estudiante`, `proctor`, `admin_examenes`, `admin_sistema` se crean como **realm roles**, no client roles. El backend lee `realm_access.roles` (no `resource_access.<client>.roles`). Mapeo correcto: `realm_access.roles` ↔ realm roles de Keycloak.

### D4 — Audience mapper en el client `proctoring-spa`

Sin un `oidc-audience-mapper` en el client, Keycloak no incluye `proctoring-api` en el claim `aud` del access token. El mapper se configura con `included.custom.audience=proctoring-api` y `access.token.claim=true`. Esto es imprescindible: sin él el backend rechaza el 100% de los tokens.

### D5 — MFA en usuarios de prueba: NO configurado (OTP queda como follow-up)

El backend (`token.py`) lee MFA del claim `amr`. En Keycloak, `amr` se rellena cuando el usuario completa un segundo factor (OTP, WebAuthn). Para que los usuarios de prueba pasen la política MFA de `ROLES_CON_MFA` (proctor, admin), se necesita o bien un OTP configurado o una política de realm que marque la sesión con `amr=otp`.

**Decisión**: Los usuarios `proctor` y `admin` de prueba NO tendrán OTP configurado en este change. El claim `amr` del token NO incluirá ningún valor de SEGUNDO_FACTOR_AMR. Resultado: `mfa_satisfecho=False` para estos usuarios. El backend construirá un `AuthenticatedPrincipal` válido pero con `mfa_satisfecho=False` — los endpoints que exigen MFA devolverán 403.

**Implicancia**: Para testear endpoints que exigen MFA, el desarrollador deberá configurar TOTP en la cuenta del usuario de prueba (vía la UI de Keycloak en `http://localhost:8080`) o configurar una `Authentication Flow` de realm que acepte `acr=1` como MFA satisfecho.

**Follow-up recomendado** (no en este change): C-53 o configurar en el realm un flow de browser que fuerce OTP para `proctor`/`admin`, o agregar un mapper de `amr` con valor `otp` para testing (solo en entornos `dev` explícitamente).

### D6 — directAccessGrantsEnabled=true en proctoring-spa

Habilitado SOLO para facilitar tests sin browser (password grant). En producción se deshabilita. Documentado como dev-only en el JSON.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| Realm JSON en repo → credenciales de dev en git | Contraseñas son dev-only, marcadas explícitamente. Credenciales de prod van por Vault (DD-5). |
| KC_HOSTNAME_URL rompe si el stack corre en otra URL | Para producción se usa KC_HOSTNAME distinto. El `.env.example` es solo para dev local. |
| `--import-realm` re-importa en cada restart si el realm no existe | Keycloak 26 NO re-importa si el realm ya existe en la BD. Idempotente. |
| Usuarios de prueba sin MFA → 403 en endpoints MFA | Documentado en D5. Es una limitación conocida de este change, con follow-up claro. |
| Port 8080 de Keycloak no expuesto en compose | Hay que agregar `ports: ["8080:8080"]` al servicio keycloak para que el browser llegue. |

## Migration Plan

1. Crear `infra/keycloak/proctoring-realm.json`.
2. Modificar `infra/docker-compose/docker-compose.yml` (command, env, volumen, ports).
3. Modificar `.env.example` (KEYCLOAK_ISSUER).
4. `docker compose up -d --force-recreate keycloak` para que tome el nuevo command + volumen.
5. Verificar import: `curl http://localhost:8080/realms/proctoring` → debe devolver JSON con `realm=proctoring`.
6. Verificar token: `curl -s -X POST http://localhost:8080/realms/proctoring/protocol/openid-connect/token -d "client_id=proctoring-spa&grant_type=password&username=ecaceres&password=test1234"` → access token con `aud: ["proctoring-api", ...]` y `iss: http://localhost:8080/realms/proctoring`.

**Rollback**: Revertir los 3 archivos cambiados y recrear el servicio. El volumen de Keycloak puede borrarse para limpiar el realm importado.

## Open Questions

- OQ-1: ¿Se quiere un mapper de `amr` fake para dev que permita testear endpoints MFA sin OTP real? (Decisión del dueño — no implementar hasta confirmar.)
- OQ-2: ¿Se expone `8080` de Keycloak directamente o via Nginx reverse proxy? Este change lo expone directo por simplicidad dev; cambio posterior puede agregar reverse proxy.
