## Context

ActiveExam ya tiene tres piezas reutilizables que este change combina en vez de reinventar:

- **`usuario`** (`app/infrastructure/persistence/models/transactional.py`): ya soporta `auth_provider` ('keycloak' | 'local', se agrega 'lti'), `debe_cambiar_password` (flag "clave temporal, cambiala en el próximo login" — ya usado por `POST /users` cuando un admin crea una cuenta), `attrs_federados` (JSONB libre — hoy vacío para altas locales, ideal para guardar el contexto LTI sin migración).
- **`emitir_jwt_propio`** (`app/infrastructure/auth/own_issuer.py`): emite el JWT propio de sesión (HS256) que ya usa `POST /auth/login`. Un launch LTI validado es una prueba de identidad al menos tan fuerte como user+password — se reusa esta misma función para autologuear al alumno tras el launch, sin pedirle contraseña (todavía no tiene una).
- **Patrón de "clave temporal"** de `POST /users` (`crear_usuario`): password aleatorio + `debe_cambiar_password=True`. El JIT de LTI sigue el mismo patrón — la cuenta nace sin contraseña usable localmente hasta que el alumno la fija.

Nada de esto requiere tocar Keycloak: el JWT propio (D-06/C-55) ya es el emisor de sesión de la plataforma; LTI es una FORMA MÁS de llegar a ese mismo JWT, no un sistema de auth paralelo.

## Goals / Non-Goals

**Goals:**
- Un alumno matriculado en el curso "ZZ Test" (campustest) hace clic en la actividad LTI, y sin pasos manuales de un admin, termina con una cuenta ActiveExam rol `alumno` y una sesión iniciada.
- La identidad (nombre, email, rol) viene SIEMPRE de un JWT firmado por Moodle, validado contra el JWKS de Moodle — nunca de un body que el navegador arma.
- Reuso máximo de lo que ya existe (`usuario`, `emitir_jwt_propio`, patrón de clave temporal) — cero tablas nuevas si el modelo actual alcanza.
- El alumno, tras el primer launch, pasa por la pantalla de cambio de contraseña ya existente (`debe_cambiar_password`) para poder loguearse directo la próxima vez sin depender de Moodle.

**Non-Goals (explícitamente fuera de este change):**
- NRPS (roster automático) — el mapeo LTI-contexto → materia/comisión es manual (admin), no se sincroniza matrícula completa.
- AGS (retorno de nota vía LTI) — el write-back de nota sigue por el REST WS existente (`core_grades_update_grades`, DD-20).
- Deep Linking (elegir qué contenido de ActiveExam se linkea desde Moodle) — el link apunta siempre al dashboard alumno.
- Soporte de más de un `iss` (LMS) simultáneo más allá de la allowlist manual — no hay descubrimiento automático de LMS.
- Multi-tenant: un solo par de claves RS256 del lado ActiveExam-como-Tool, no una por institución.

## Decisions

**D1 — Reusar `usuario` con `auth_provider='lti'`, sin tabla nueva de usuarios LTI.**
Alternativa descartada: tabla separada `usuario_lti`. Se descarta porque duplicaría lógica de roles/soft-delete/auditoría que `usuario` ya resuelve. `id_institucional` (UNIQUE) guarda `lti:{deployment_id}:{sub}` — namespacing por deployment evita colisión entre dos Moodles que reusen el mismo `sub` numérico.

**D2 — Sí se necesita UNA tabla nueva: `lti_deployment_confiable`.**
Guarda qué `(iss, deployment_id, client_id)` de Moodle son de confianza y a qué `materia_id`/`comision_id` de ActiveExam mapea ese contexto de curso. Sin esto, cualquier `iss` podría lanzar un launch válido con SU PROPIA clave (si alguien levanta un Moodle propio y se auto-registra) — la confianza no es "el JWT está bien firmado", es "está bien firmado Y el emisor es uno que dimos de alta". Alternativa descartada: allowlist en variable de entorno — se prefiere tabla porque el mapeo curso→comisión es dato operativo que cambia sin deploy.

**D3 — Claves RS256 propias de ActiveExam-como-Tool, separadas del JWT de sesión (HS256).**
El JWT de sesión (`emitir_jwt_propio`) es HS256 simétrico — sirve para que ActiveExam se valide a sí mismo, no para que un tercero (Moodle) verifique nada nuestro. LTI exige que el Tool exponga un JWKS público (`GET /lti/jwks`) con clave RS256 (asimétrica) para que Moodle pueda, a su vez, verificar mensajes firmados por ActiveExam (hoy no enviamos ninguno firmado hacia Moodle en este alcance mínimo, pero el registro dinámico exige publicar el JWKS igual — parte del contrato IMS). Se generan y guardan cifradas (mismo mecanismo ya usado para `moodle_credencial`).

**D4 — Auto-login inmediato tras launch válido, no un paso intermedio de "confirmar identidad".**
Un launch LTI validado (firma + nonce + audience + expiración, todo correcto) es prueba de identidad suficiente — pedirle al alumno que además ponga una contraseña ANTES de dejarlo entrar sería más fricción que un login normal, no menos. Se emite el JWT de sesión directo (vía `emitir_jwt_propio`) y se redirige al frontend con el token; recién en el dashboard (ya autenticado) se lo dirige a "fijá tu contraseña" vía el `debe_cambiar_password` existente.

**D5 — `nonce` con expiración corta en Postgres, no cache en memoria.**
El flujo OIDC de LTI exige validar que el `nonce` del `state` en `/lti/login` coincida con el del `id_token` en `/lti/launch`, y que no se reuse (replay). Con múltiples workers/instancias, memoria de proceso no sirve — se persiste `nonce` + `state` + expiración (5 min) en una tabla chica, con índice + limpieza por TTL (mismo patrón que `refresh_tokens`).

## Risks / Trade-offs

- **[Riesgo] Superficie nueva de auth pública (`/lti/login`, `/lti/launch`) sin autenticación previa.** → Mitigación: D2 (allowlist de `iss`/`deployment_id`), validación estricta de firma/nonce/audiencia/expiración, rate limiting igual que `/auth/login`, y NO se habilita contra un curso real de producción hasta pasar revisión de seguridad — solo contra `ZZ Test` en campustest (entorno de prueba).
- **[Riesgo] JIT crea una cuenta por cada clic, incluso de gente que prueba sin ser alumno real del curso.** → Mitigación: el launch solo es válido si Moodle lo emite desde un contexto de curso donde el usuario está inscripto (esto ya lo garantiza Moodle del lado emisor — el link LTI solo aparece dentro del curso a sus matriculados); además D2 acota a los `iss` dados de alta.
- **[Riesgo] Claves RS256 del Tool comprometidas.** → Mitigación: mismo cifrado at-rest que `moodle_credencial`, rotación soportada (JWKS puede publicar 2 claves durante transición).
- **[Trade-off] Mapeo curso→comisión manual (no NRPS).** Aceptado por alcance: un admin configura `lti_deployment_confiable` una vez por curso: bajo volumen, no bloquea el caso de uso pedido (un curso de prueba).

## Migration Plan

1. Migración aditiva: tabla `lti_deployment_confiable` + tabla `lti_nonce` (o reuso de una tabla de nonces genérica si ya existe un patrón similar — a confirmar en tasks). `usuario.auth_provider` ya acepta cualquier string (no es un enum de DB), así que `'lti'` no requiere migración de columna.
2. Backend: nuevo router `lti`, servicio de validación de launch, JIT provisioning.
3. Frontend: nada nuevo si D4 se cumple — el flujo de "cambiar contraseña obligatorio" y el dashboard alumno ya existen; el único agregado es la landing que recibe el `access_token`/`refresh_token` por redirect y los persiste (mismo mecanismo que un login normal).
4. Prueba en entorno: registrar ActiveExam como herramienta externa en `ZZ Test` (campustest), exponiendo el backend local vía `cloudflared` durante la sesión de prueba — NO como mecanismo permanente.
5. Rollback: la tabla `lti_deployment_confiable` vacía = ningún `iss` confiable = el endpoint de launch rechaza todo (falla cerrado, no abierto).

## Open Questions

- ¿El mapeo curso→comisión lo carga un admin a mano en una pantalla nueva, o alcanza con un insert directo para la prueba de `ZZ Test` y se posterga la UI de administración a un change futuro? (Para el alcance de "probar que funciona" alcanza con el insert; la UI queda como tarea marcada pero de prioridad baja en `tasks.md`.)
- ¿Se persiste el curso/contexto LTI en `attrs_federados` del usuario, o solo se usa para resolver `comision_id` al momento del JIT y no se vuelve a guardar? (Propuesta: se guarda un resumen mínimo — `deployment_id`, `context_id`, fecha del último launch — útil para auditoría, sin duplicar el roster completo.)
