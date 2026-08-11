## 1. Migración y modelos

- [x] 1.1 Migración `lti_deployment_confiable` (iss, deployment_id, client_id, jwks_uri, context_id→comision_id nullable, activo) — `0063`
- [x] 1.2 Migración `lti_nonce` (nonce, state, iss, expira_en) — mismo patrón TTL que `refresh_tokens` — `0064` (+ `consumido_en` anti-replay)
- [x] 1.3 Modelo SQLAlchemy `LtiDeploymentConfiableModel` + `LtiNonceModel` (+ `LtiToolKeyModel`) en `models/lti.py`, registrados en `__init__.py` y conftest
- [x] 1.4 Generación y persistencia cifrada del par de claves RS256 del Tool (`infrastructure/lti/keys.py`, `SecretCipher`; tabla `lti_tool_key` migr `0065`)

## 2. JWKS y registro dinámico (lti-tool-provider)

- [x] 2.1 Test: `GET /lti/jwks` devuelve un JWK Set válido con la clave pública vigente (+ idempotente)
- [x] 2.2 Implementar `GET /lti/jwks` (genera el par perezosamente vía `asegurar_tool_key_activa`)
- [x] 2.3 Test: `GET /lti/dynamic-registration` devuelve la config IMS esperada (initiate_login_uri, redirect_uris, jwks_uri)
- [x] 2.4 Implementar `GET /lti/dynamic-registration`

## 3. Login OIDC (lti-tool-provider)

- [x] 3.1 Test: login desde deployment confiable genera state+nonce persistidos y redirige a Moodle
- [x] 3.2 Test: login desde deployment NO confiable se rechaza sin generar state/nonce (403, falla cerrado)
- [x] 3.3 Implementar `GET /lti/login` (RED→GREEN de 3.1 y 3.2)
- [x] 3.4 Job/limpieza de nonces expirados (TTL 5 min) — limpieza oportunista en `/lti/login` (DELETE expira_en < now), sin scheduler

## 4. Validación de launch (lti-tool-provider)

- [x] 4.1 Test: launch con id_token válido (firma+nonce+aud+exp correctos) se acepta (+ consume nonce)
- [x] 4.2 Test: firma inválida → rechazo, sin crear/loguear usuario
- [x] 4.3 Test: nonce reusado (replay) → rechazo
- [x] 4.4 Test: token expirado → rechazo
- [x] 4.5 Test: audiencia (aud) no coincide con client_id registrado → rechazo
- [x] 4.6 Implementar `POST /lti/launch` + `validar_launch` (RED→GREEN de 4.1-4.5). NOTA: es POST (response_mode=form_post de LTI), no GET como decía el título de la task

## 5. JIT provisioning (lti-jit-provisioning)

- [x] 5.1 Test: primer launch de un sub nuevo crea usuario con roles=["estudiante"] (rol canónico; spec dice "alumno" informalmente), auth_provider="lti", debe_cambiar_password=true, datos SOLO del id_token
- [x] 5.2 Test: segundo launch del mismo sub NO duplica la cuenta, reusa la existente
- [x] 5.3 Test: el JIT ignora cualquier dato de identidad que no venga del id_token validado (la firma de provisionar_o_recuperar_usuario no acepta parámetros extra de identidad — diseño anti-inyección)
- [x] 5.4 Implementar servicio de JIT provisioning (RED→GREEN de 5.1-5.3) — `app/application/lti/jit_provisioning.py`
- [x] 5.5 Test: tras JIT/login exitoso se emite JWT de sesión propio (mismo emisor que /auth/login) sin pedir password — test puro GREEN
- [x] 5.6 Implementar emisión de sesión + redirect al frontend con el token — endpoint `/lti/launch` actualizado en `router.py` + `main_slim.py` cableado
- [x] 5.7 Test: context_id con mapeo configurado matricula al alumno en la comisión mapeada
- [x] 5.8 Test: context_id sin mapeo crea/loguea igual pero sin matricular
- [x] 5.9 Implementar resolución de mapeo context_id→comision_id (RED→GREEN de 5.7-5.8) — `_asegurar_matricula` con INSERT ON CONFLICT DO NOTHING

## 6. Allowlist admin (lti-trust-config)

- [x] 6.1 Test: tabla vacía rechaza cualquier login/launch (falla cerrado) — `test_tabla_vacia_login_rechaza`
- [x] 6.2 Test: admin_sistema puede crear/editar/borrar filas de lti_deployment_confiable — `test_admin_{crea,lista,edita,borra}_deployment`
- [x] 6.3 Test: usuario sin rol admin_sistema recibe 403 al intentar gestionar el allowlist — `test_estudiante_no_puede_gestionar_403` (+ `test_sin_token_401`)
- [x] 6.4 Implementar endpoints CRUD admin-only para `lti_deployment_confiable` — `admin/lti_router.py` (`create_lti_admin_router`), cableado en `main_slim.py`

## 7. Frontend

- [x] 7.1 Landing `/lti-login` (`screens/LtiLanding.tsx`) recibe access_token/refresh_token del redirect y los persiste vía `authStore.loginWithTokens` → `JwtAdapter.seedSession` (mismas claves sessionStorage que el login normal). Tests en `jwt.test.ts` (seedSession happy + falla-cerrado). Ruta pública agregada en `App.tsx`.
- [x] 7.2 Gate "fijá tu contraseña" ya existe en `RequireAuth` (dispara ante `principal.debe_cambiar_password`). El flujo LTI lo dispara igual: la landing hidrata el principal → el store enriquece con `GET /auth/me` (trae `debe_cambiar_password`) → `RequireAuth` intercepta antes de cualquier ruta protegida.

## 8. Prueba en vivo contra campustest (ZZ Test)

- [x] 8.1 Exponer el backend local vía `cloudflared` (URL HTTPS temporal) — túnel a `http://localhost:8000`; fix infra: uvicorn con `--proxy-headers --forwarded-allow-ips="*"` (dev compose + Dockerfile.slim) para que las URLs salgan `https://` a través del túnel
- [x] 8.2 Registrar ActibeExam como herramienta externa en campustest — herramienta preconfigurada LTI 1.3 (id=1), URLs del túnel (launch/login/jwks/redirect). NOTA: registro MANUAL (no dinámico). Requirió promover `emiliano_caceres` a Administrador del sitio (era Manager sin site:config) vía cuenta admin Alberto Cortez.
- [x] 8.3 Deployment dado de alta en `lti_deployment_confiable`: iss=`https://campustest.frm.utn.edu.ar`, client_id=`6w1huGZSwii82yL`, deployment_id=`1`, jwks_uri=`.../mod/lti/certs.php`, mapeado a Programación 1 / Comisión 1.
- [x] 8.4 Actividad "Herramienta externa" (ActibeExam — Rendir examen) agregada en ZZ Test (courseid=7, cmid=1443), launch container = Nueva ventana.
- [x] 8.5 Flujo E2E como alumno VERDE: clic en Moodle → login OIDC (POST) → launch validado → cuenta `lti:1:7` creada (nombre/email de claims, roles=estudiante, auth_provider=lti) → matriculado en Comisión 1 por el mapeo → dashboard `/alumno` → gate "Definí tu contraseña". Captura: `c75-lti-launch-dashboard-alumno.png`. Bugs encontrados y arreglados: `/lti/login` faltaba aceptar POST (405); clock skew Moodle↔contenedor (~90s) → `leeway=300s` en `jwt.decode`; uvicorn `--proxy-headers` para HTTPS por el túnel.
- [x] 8.6 Documentado. HALLAZGO RESUELTO (decisión del dueño): el alumno LTI en su PRIMER ingreso define contraseña (para poder entrar luego directo con el link), y del 2do launch en adelante entra directo. Implementado: `/auth/me` expone `auth_provider`; `PUT /auth/change-password` permite el primer set de un usuario LTI (auth_provider=lti + debe_cambiar_password) SIN pedir la contraseña actual (el Bearer de la sesión LTI válida prueba identidad); frontend `CambioClaveObligatorio` muestra variante LTI (sin campo "temporal"). Verificado en vivo: 1er launch→define pass→dashboard; 2do launch→directo. Tests: `test_c75_lti_password_setup.py` (3). Captura: `c75-lti-dashboard-post-password.png`. Túnel cloudflared = temporal; para uso más allá de ZZ Test → deploy real (pendiente, fuera de este change).

## 9. Gobernanza y cierre

- [ ] 9.1 Revisión de seguridad del endpoint público antes de considerar el change listo para algo más que `ZZ Test` (dominio CRÍTICO — Auth)
- [ ] 9.2 `openspec archive` una vez todas las tasks estén en verde y la prueba en vivo (sección 8) esté documentada
