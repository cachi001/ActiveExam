> **Estado al archivar (2026-06-11)**: configuración Keycloak completa y lista en infra. **Activación diferida**: el backend usa hoy JWT propio (HS256, ver C-55 archivado); Keycloak quedará habilitado cuando la integración LMS (DD-20: LTI 1.3 + plugin Moodle) entre en marcha. Ajustado: realm tiene **3 roles reales** (`estudiante`, `proctor`, `admin_sistema`) — el rol `admin_examenes` original se descarta (no se crean exámenes en plataforma, ver C-44 cancelado).

## 1. Directorio y estructura de archivos de infra

- [x] 1.1 Crear directorio `infra/keycloak/` si no existe

## 2. Realm JSON de Keycloak

- [x] 2.1 Crear `infra/keycloak/proctoring-realm.json` con configuración del realm `proctoring` (enabled=true, sslRequired=none para dev, loginWithEmailAllowed=true, registrationAllowed=false)
- [x] 2.2 Agregar los **3 realm roles** en el JSON: `estudiante`, `proctor`, `admin_sistema` (ajuste: `admin_examenes` no aplica — no hay UI de creación de exámenes)
- [x] 2.3 Agregar el client `proctoring-spa` en el JSON: publicClient=true, standardFlowEnabled=true, directAccessGrantsEnabled=true, pkce.code.challenge.method=S256, redirectUris incluye localhost + `active-exam.vercel.app`, webOrigins `["+"]`
- [x] 2.4 Agregar `oidc-audience-mapper` en el client `proctoring-spa` con `included.custom.audience=proctoring-api`, `access.token.claim=true`, `id.token.claim=false`
- [x] 2.5 Agregar usuario `ecaceres` con credential password `test1234` y rol realm `estudiante`
- [x] 2.6 Agregar usuario `cferreyra` con credential password `test1234` y rol realm `proctor`
- [x] 2.7 Agregar usuario `admin` con credential password `test1234` y rol realm `admin_sistema` (ajuste: solo `admin_sistema`)
- [x] 2.8 Verificar que el JSON sea válido — Verificado 2026-06-11 con `node -e JSON.parse(...)` → "JSON valido"

## 3. Docker Compose — servicio keycloak

- [x] 3.1 `command: start-dev --import-realm` en el servicio `keycloak` de `infra/docker-compose/docker-compose.yml`
- [x] 3.2 `KC_HOSTNAME_URL: "http://localhost:8080"` agregado al servicio `keycloak`
- [x] 3.3 Volumen read-only del realm JSON: `infra/keycloak/proctoring-realm.json:/opt/keycloak/data/import/proctoring-realm.json:ro`
- [x] 3.4 Puerto `8080:8080` expuesto

## 4. Variables de entorno (.env.example)

- [x] 4.1 `KEYCLOAK_ISSUER=http://localhost:8080/realms/proctoring` en `.env.example`
- [x] 4.2 `KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs` sin cambios (backchannel interno Docker)
- [x] 4.3 Comentario inline explicativo en `.env.example` sobre asimetría localhost vs keycloak (issuer = hostname del browser, jwks = backchannel docker interno)

## 5. Verificación estática (sin stack)

- [x] 5.1 JSON válido — Verificado con `node -e JSON.parse(...)`
- [x] 5.2 Realm JSON contiene `realm=proctoring`, `enabled=true`, 3 roles, 3 usuarios, client `proctoring-spa` con audience mapper
- [x] 5.3 Sin modificaciones a `.py`/`.ts`/`.tsx` — solo archivos de infra y `.env.example`
- [x] 5.4 `openspec validate --strict` ejecutado durante archivado
