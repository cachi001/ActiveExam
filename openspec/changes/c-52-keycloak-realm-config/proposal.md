## Why

Keycloak corre en `start-dev` sin realm configurado: no hay realm `proctoring`, no hay clients, no hay usuarios de prueba ni audience mapper. Cualquier intento de login o validación de token falla en el backend porque el claim `aud` nunca contiene `proctoring-api` y el `iss` del token difiere del `KEYCLOAK_ISSUER` configurado. Este change crea la fundación de identidad de la que dependen todos los cambios posteriores con auth real (frontend OIDC, integración E2E).

## What Changes

- **Nuevo**: realm `proctoring` en Keycloak con configuración completa de seguridad (HTTPS deshabilitado en dev, PKCE obligatorio, refresh tokens rotantes).
- **Nuevo**: 4 realm roles exactos que reconoce el backend: `estudiante`, `proctor`, `admin_examenes`, `admin_sistema`.
- **Nuevo**: 3 usuarios de prueba con contraseña conocida (`test1234`, email verificado): `ecaceres` (estudiante), `cferreyra` (proctor), `admin` (admin_examenes + admin_sistema).
- **Nuevo**: client SPA público `proctoring-spa` (OIDC, PKCE S256, directAccessGrants para test sin browser).
- **Nuevo**: `oidc-audience-mapper` en el client que inyecta `proctoring-api` en el claim `aud` del access token — sin esto el backend rechaza TODO token.
- **Modificado**: `docker-compose.yml` del servicio `keycloak`: command `start-dev --import-realm`, env `KC_HOSTNAME_URL=http://localhost:8080`, volumen del realm JSON read-only.
- **Modificado**: `.env.example` — `KEYCLOAK_ISSUER` pasa de `http://keycloak:8080/...` a `http://localhost:8080/...` para matchear el `iss` real del token (que se forma con el hostname expuesto al browser).
- **Nuevo**: `infra/keycloak/proctoring-realm.json` — realm JSON importable por Keycloak.

## Capabilities

### New Capabilities

- `keycloak-realm-bootstrap`: Configuración declarativa del realm `proctoring` — roles, usuarios de prueba, client SPA con PKCE y audience mapper — importable automáticamente al arrancar el contenedor.

### Modified Capabilities

- `contextual-rbac`: El rol del token ahora viene de un claim real (`realm_access.roles`) con valores provistos por el realm importado. No hay cambio en los *requisitos* del spec, pero el realm JSON es el artefacto que los satisface en entorno real.

## Impact

- `infra/keycloak/proctoring-realm.json` — archivo nuevo (creado por este change).
- `infra/docker-compose/docker-compose.yml` — servicio `keycloak`: command, env KC_HOSTNAME_URL, volumen.
- `.env.example` — línea `KEYCLOAK_ISSUER` y comentario explicativo sobre la asimetría localhost vs keycloak.
- Cero archivos `.py` / `.ts` / `.tsx` tocados.
- El stack existente puede levantarse sin `.env` modificado manualmente si se usa `.env.example` como base — el volumen y el comando aseguran el import automático.
