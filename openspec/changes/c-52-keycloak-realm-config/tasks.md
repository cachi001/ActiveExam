## 1. Directorio y estructura de archivos de infra

- [ ] 1.1 Crear directorio `infra/keycloak/` si no existe

## 2. Realm JSON de Keycloak

- [ ] 2.1 Crear `infra/keycloak/proctoring-realm.json` con configuración del realm `proctoring` (enabled=true, sslRequired=none para dev, loginWithEmailAllowed=true, registrationAllowed=false)
- [ ] 2.2 Agregar los 4 realm roles en el JSON: `estudiante`, `proctor`, `admin_examenes`, `admin_sistema`
- [ ] 2.3 Agregar el client `proctoring-spa` en el JSON: publicClient=true, standardFlowEnabled=true, directAccessGrantsEnabled=true, pkce.code.challenge.method=S256, redirectUris `["http://localhost:5173/*","http://localhost:8080/*","http://localhost/*"]`, webOrigins `["+"]`
- [ ] 2.4 Agregar `oidc-audience-mapper` en el client `proctoring-spa` con `included.custom.audience=proctoring-api`, `access.token.claim=true`, `id.token.claim=false`
- [ ] 2.5 Agregar usuario `ecaceres` (firstName=Emiliano, lastName=Cáceres, email=ecaceres@frm.utn.edu.ar, emailVerified=true, enabled=true) con credential de tipo `password` valor `test1234` (temporary=false) y rol realm `estudiante`
- [ ] 2.6 Agregar usuario `cferreyra` (firstName=Carolina, lastName=Ferreyra, email=cferreyra@frm.utn.edu.ar, emailVerified=true, enabled=true) con credential password `test1234` y rol realm `proctor`
- [ ] 2.7 Agregar usuario `admin` (email=admin@proctoring.local, emailVerified=true, enabled=true) con credential password `test1234` y roles realm `admin_examenes` + `admin_sistema`
- [ ] 2.8 Verificar que el JSON sea válido (sin errores de sintaxis) con `python3 -m json.tool infra/keycloak/proctoring-realm.json > /dev/null`

## 3. Docker Compose — servicio keycloak

- [ ] 3.1 Cambiar `command: start-dev` a `command: start-dev --import-realm` en el servicio `keycloak` de `infra/docker-compose/docker-compose.yml`
- [ ] 3.2 Agregar env var `KC_HOSTNAME_URL: "http://localhost:8080"` al servicio `keycloak` (fija el claim `iss` al hostname expuesto al browser)
- [ ] 3.3 Agregar montaje de volumen read-only del realm JSON: `- ../../infra/keycloak/proctoring-realm.json:/opt/keycloak/data/import/proctoring-realm.json:ro`
- [ ] 3.4 Agregar exposición de puerto `8080:8080` al servicio `keycloak` (el browser necesita llegar a Keycloak para el flujo OIDC)

## 4. Variables de entorno (.env.example)

- [ ] 4.1 Cambiar `KEYCLOAK_ISSUER=http://keycloak:8080/realms/proctoring` a `KEYCLOAK_ISSUER=http://localhost:8080/realms/proctoring` en `.env.example`
- [ ] 4.2 Mantener `KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs` sin cambios (backchannel interno Docker)
- [ ] 4.3 Agregar comentario inline explicativo en `.env.example` junto a KEYCLOAK_ISSUER y KEYCLOAK_JWKS_URL explicando la asimetría localhost vs keycloak (issuer = hostname del browser, jwks = backchannel docker interno)

## 5. Verificación estática (sin stack)

- [ ] 5.1 Confirmar que `python3 -m json.tool infra/keycloak/proctoring-realm.json` no retorna error (JSON válido)
- [ ] 5.2 Confirmar que el realm JSON contiene exactamente los campos requeridos: `realm=proctoring`, `enabled=true`, roles, usuarios, client `proctoring-spa` y el audience mapper
- [ ] 5.3 Confirmar que no se modificó ningún archivo `.py`, `.ts`, `.tsx` (verificar con `git diff --name-only` — solo deben aparecer archivos de infra y .env.example)
- [ ] 5.4 Ejecutar `openspec validate --strict` y confirmar que pasa sin errores
