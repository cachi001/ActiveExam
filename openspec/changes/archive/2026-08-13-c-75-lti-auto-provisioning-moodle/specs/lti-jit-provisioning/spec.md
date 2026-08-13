## ADDED Requirements

### Requirement: Alta JIT de cuenta alumno desde un launch LTI validado

Tras un launch LTI validado (ver `lti-tool-provider`), si el `sub` del token (namespaced como `lti:{deployment_id}:{sub}`) no corresponde a ningún `usuario.id_institucional` existente, el sistema SHALL crear un usuario nuevo con: `roles=["alumno"]`, `auth_provider="lti"`, `nombre`/`email` tomados de los claims estándar del `id_token` (`name`, `email` — NUNCA de un body separado que el cliente pudiera manipular), `password_hash` aleatorio no comunicado, y `debe_cambiar_password=true`.

#### Scenario: Primer launch de un alumno nuevo

- **WHEN** un alumno hace el primer launch LTI y su `sub` no existe en `usuario`
- **THEN** el sistema crea la cuenta con rol `alumno`, `auth_provider='lti'`, `debe_cambiar_password=true`, y los datos personales tomados del `id_token`

#### Scenario: El cliente no puede inyectar datos de identidad

- **WHEN** se procesa el JIT provisioning
- **THEN** el sistema usa EXCLUSIVAMENTE los claims del `id_token` ya validado — ningún campo de nombre/email/rol se lee de un parámetro de query ni de un body adicional

### Requirement: Login automático tras launch validado

Tras un launch LTI validado y resuelto el usuario (creado o preexistente), el sistema SHALL emitir un JWT de sesión propio (mismo emisor que `POST /auth/login`, `emitir_jwt_propio`) sin requerir contraseña, y redirigir al frontend con el token. El alumno NO debe volver a autenticarse manualmente en este primer acceso.

#### Scenario: Alumno nuevo entra directo al dashboard

- **WHEN** el JIT provisioning crea la cuenta y el launch fue válido
- **THEN** el sistema emite el JWT de sesión y redirige al alumno autenticado al dashboard, donde ve el aviso de "fijá tu contraseña" (por `debe_cambiar_password=true`)

#### Scenario: Alumno existente vuelve a hacer launch

- **WHEN** un alumno cuyo `sub` LTI ya tiene cuenta hace un nuevo launch válido
- **THEN** el sistema NO crea una cuenta duplicada, reusa la existente, y emite el JWT de sesión igual

### Requirement: Mapeo de contexto LTI a materia/comisión

El sistema SHALL resolver, a partir del `context_id`/`deployment_id` del launch, la `comision_id` de ActiveExam configurada en `lti_deployment_confiable` para ese contexto, y usarla para matricular al alumno si corresponde (mismo mecanismo que la auto-matriculación por código existente).

#### Scenario: Contexto mapeado a una comisión

- **WHEN** el launch trae un `context_id` que tiene mapeo configurado a una comisión
- **THEN** el alumno queda matriculado en esa comisión tras el JIT (si no lo estaba ya)

#### Scenario: Contexto sin mapeo configurado

- **WHEN** el launch trae un `context_id` sin mapeo configurado
- **THEN** el sistema crea/loguea la cuenta igual, pero SIN matricularla en ninguna comisión, y lo registra para que un admin complete el mapeo
