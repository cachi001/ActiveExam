## ADDED Requirements

### Requirement: Registro dinámico de ActiveExam como herramienta LTI

El sistema SHALL exponer `GET /api/v1/lti/dynamic-registration` como endpoint PÚBLICO que responde con la configuración del Tool siguiendo el spec de registro dinámico de IMS (1EdTech): nombre del Tool, endpoints de login/launch/JWKS, scopes soportados. Moodle consulta este endpoint una única vez al registrar ActiveExam como herramienta externa.

#### Scenario: Registro dinámico exitoso

- **WHEN** un administrador de Moodle pega la URL de registro dinámico en "Gestionar herramientas"
- **THEN** Moodle recibe una respuesta con `initiate_login_uri`, `redirect_uris`, `jwks_uri`, y los claims soportados, y completa el registro sin pasos manuales adicionales

### Requirement: JWKS público del Tool

El sistema SHALL exponer `GET /api/v1/lti/jwks` con las claves públicas RS256 vigentes de ActiveExam-como-Tool, en formato JWK Set estándar. Las claves privadas correspondientes MUST persistirse cifradas at-rest (mismo mecanismo que `moodle_credencial`).

#### Scenario: Moodle valida un mensaje firmado por ActiveExam

- **WHEN** Moodle necesita verificar la firma de un mensaje emitido por ActiveExam
- **THEN** obtiene la clave pública vigente desde `/lti/jwks` y la validación es correcta

### Requirement: Login OIDC iniciado por Moodle

El sistema SHALL exponer `GET /api/v1/lti/login` que recibe `iss`, `login_hint`, `target_link_uri` y `lti_deployment_id` de Moodle, valida que el `iss`/`deployment_id` estén en la allowlist de confianza (`lti_deployment_confiable`), genera `state` y `nonce` con expiración corta (5 minutos) persistidos en base, y redirige de vuelta al endpoint de autorización de Moodle.

#### Scenario: Login iniciado desde un deployment confiable

- **WHEN** Moodle inicia el login OIDC con un `iss`/`deployment_id` que está en la allowlist
- **THEN** el sistema genera `state`+`nonce`, los persiste, y redirige a Moodle para continuar el flujo

#### Scenario: Login iniciado desde un deployment NO confiable

- **WHEN** Moodle (o cualquier otro emisor) inicia el login OIDC con un `iss`/`deployment_id` que NO está en la allowlist
- **THEN** el sistema rechaza el login sin generar `state`/`nonce` ni redirigir

### Requirement: Validación del launch LTI

El sistema SHALL exponer `GET /api/v1/lti/launch` que recibe el `id_token` (JWT) firmado por Moodle, y MUST validar: firma contra el JWKS del `iss` (obtenido de la config del deployment confiable), `nonce` (coincide con el emitido en `/lti/login` y no fue usado antes), `state`, audiencia (`aud` = client_id registrado), expiración (`exp`), y tipo de mensaje (`LtiResourceLinkRequest`). Si CUALQUIERA de estas validaciones falla, el sistema MUST rechazar el launch sin crear ni loguear ningún usuario.

#### Scenario: Launch válido

- **WHEN** Moodle envía un `id_token` con firma, nonce, audiencia y expiración correctos
- **THEN** el sistema acepta el launch y continúa con el JIT provisioning (ver capability `lti-jit-provisioning`)

#### Scenario: Firma inválida

- **WHEN** el `id_token` no valida contra el JWKS del `iss`
- **THEN** el sistema rechaza el launch con 401/403 y no crea ni loguea ningún usuario

#### Scenario: Nonce reusado (replay)

- **WHEN** el `nonce` del `id_token` ya fue consumido por un launch anterior
- **THEN** el sistema rechaza el launch como posible replay y no crea ni loguea ningún usuario

#### Scenario: Token expirado

- **WHEN** el `id_token` tiene `exp` en el pasado
- **THEN** el sistema rechaza el launch
