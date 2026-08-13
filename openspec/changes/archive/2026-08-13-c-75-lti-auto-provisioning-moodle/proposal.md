## Why

Hoy un alumno de un curso Moodle (ej. "ZZ Test" en campustest) no tiene forma de entrar a ActiveExam sin que alguien le cree la cuenta a mano primero. El pedido es que, desde un link/actividad dentro del curso en Moodle, el alumno llegue directo a ActiveExam con su cuenta ya creada (rol `alumno`) y pueda fijar su contraseña en el momento.

La superficie ingenua de esto — un POST desde el navegador del alumno con "los datos que dice Moodle" — es falsificable: cualquiera podría mandar un POST con el nombre/email de otra persona y crearle una cuenta con rol alumno a su nombre. El proyecto ya tiene la decisión arquitectónica correcta documentada para este problema (DD-20, `knowledge-base/09_decisiones_y_supuestos.md`): **LTI 1.3** como capa universal de integración con LMS — el LMS firma criptográficamente los datos del alumno (JWT) y ActiveExam los valida contra la clave pública de Moodle antes de confiar en ellos. Ningún dato de identidad viaja sin firmar.

Este change implementa el **Tool Provider LTI 1.3 mínimo viable**: registro dinámico, login OIDC, validación de launch, y JIT provisioning de la cuenta alumno — alcance acotado a lo que hace falta para que el flujo "clic en Moodle → cuenta creada → fijar contraseña → dashboard alumno" funcione, sin construir todavía NRPS (roster) ni AGS (retorno de notas vía LTI, que hoy ya se resuelve por el REST WS existente, `core_grades_update_grades`, D12/DD-20).

## What Changes

- Nuevo endpoint de **registro dinámico LTI** (`GET /lti/dynamic-registration`) que Moodle consulta al registrar ActiveExam como herramienta externa — devuelve la configuración del Tool (client ID a emitir, JWKS, endpoints) siguiendo el spec de registro dinámico de IMS.
- Nuevo par de endpoints del **flujo OIDC de login** LTI: `GET /lti/login` (recibe el `iss`/`login_hint`/`target_link_uri` de Moodle, redirige con `state`+`nonce`) y `GET /lti/launch` (recibe el `id_token` firmado, valida firma contra el JWKS de Moodle, valida `nonce`/`state`/audience/expiración).
- **JIT provisioning**: si el `sub` del token LTI no tiene usuario en ActiveExam, se crea uno con rol `alumno`, poblado desde los claims estándar del token (nombre, email, `lti_deployment_id`, contexto del curso) — nunca desde datos que el cliente pudiera mandar sueltos.
- Redirección post-launch a una pantalla de **"fijar contraseña"** (cuenta recién creada, sin password local todavía) o directo al dashboard alumno (cuenta ya existente y logueada).
- Persistencia de las claves JWT de ActiveExam como Tool (par de claves RS256 para firmar/exponer el JWKS propio) — reutiliza la infraestructura de secretos ya usada para JWT propio (`jwt-own-issuer`).
- Config nueva: registro de qué `iss`/`deployment_id` de Moodle son confiables (allowlist), y a qué `materia`/`comision` de ActiveExam mapea cada contexto LTI (curso) — mínimo viable: mapeo manual admin, no automático.
- **Fuera de alcance de este change** (documentado, no implementado): NRPS (roster automático), AGS (retorno de nota vía LTI — sigue por REST WS), Deep Linking (selección de contenido), soporte multi-LMS más allá de Moodle.

## Capabilities

### New Capabilities
- `lti-tool-provider`: registro dinámico + login OIDC + validación de launch LTI 1.3 (Tool Provider del lado de ActiveExam).
- `lti-jit-provisioning`: creación de cuenta `alumno` a partir de un launch LTI validado, mapeo de claims → usuario, y redirección a fijar contraseña o al dashboard.
- `lti-trust-config`: configuración admin de emisores (`iss`)/deployments Moodle confiables y su mapeo a materia/comisión.

### Modified Capabilities
- `user-registration`: se agrega un segundo camino de alta de usuario (JIT vía LTI), además del registro manual existente.

## Impact

- **Backend**: nuevo router `app/presentation/api/v1/lti/`, nuevo servicio de aplicación (validación de launch, JIT provisioning), nuevas tablas (`lti_deployment_confiable`, o extender `usuario` con `origen='lti'` + `lti_sub`), nueva dependencia de librería JWT/JWKS (si no alcanza lo ya usado para JWT propio).
- **Frontend**: pantalla nueva "Fijar tu contraseña" (cuenta creada por LTI, primer acceso).
- **Moodle (campustest)**: registro de ActiveExam como herramienta externa (LTI 1.3, registro dinámico) en el curso "ZZ Test" — lo hace un admin de Moodle (`emiliano_caceres` tiene el permiso), fuera del código de este repo.
- **Gate de gobernanza**: dominio de autenticación/alta de cuentas = **CRÍTICO** (Auth). Cada endpoint nuevo debe pasar por revisión antes de habilitarse contra un curso real, más allá del entorno de prueba (`ZZ Test`, campustest).
