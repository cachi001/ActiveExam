## ADDED Requirements

### Requirement: Solicitud de vía alternativa queda en estado pendiente hasta habilitación humana
Cuando un alumno elige la vía alternativa (RN-CO-05), el sistema SHALL registrar una `SolicitudViaAlternativa` con estado `pendiente_proctor` en la tabla `solicitudes_via_alternativa`. El alumno NO podrá rendir hasta que un proctor o administrador cambie el estado a `habilitado_por_proctor`. El sistema SHALL rechazar cualquier intento de rendir mientras el estado sea `pendiente_proctor`, retornando código `via_alternativa_pendiente` con un mensaje claro.

#### Scenario: Alumno solicita vía alternativa — estado persiste como pendiente
- **WHEN** el alumno llama `POST /api/v1/consent/alternative` eligiendo vía alternativa
- **THEN** el sistema crea un registro en `solicitudes_via_alternativa` con `estado = pendiente_proctor`
- **THEN** la respuesta incluye `estado: "pendiente_proctor"` y `puede_rendir: false`

#### Scenario: Gate bloquea al alumno pendiente de habilitación
- **WHEN** `puedeRendir()` se evalúa para un alumno con solicitud en estado `pendiente_proctor`
- **THEN** el sistema retorna `{ puede: false, codigo: "via_alternativa_pendiente", razon: "Tu verificación alternativa está pendiente de aprobación de un proctor." }`
- **THEN** el alumno NO navega a `/sala-espera` ni puede iniciar el examen

#### Scenario: Frontend muestra pantalla de espera informativa
- **WHEN** el alumno completa el flujo de solicitud de vía alternativa en `Consent.tsx` o `EnrollmentConsentStep.tsx`
- **THEN** se muestra un card informativo con el mensaje "Tu solicitud quedó registrada. Un proctor verificará tu identidad antes de habilitarte."
- **THEN** NO se navega a `/sala-espera`
- **THEN** el botón "No acepto — solicitar vía alternativa" queda deshabilitado o la pantalla cambia a estado de espera

### Requirement: Proctor habilita manualmente una solicitud de vía alternativa pendiente
El sistema SHALL proveer un endpoint `POST /api/v1/consent/alternative/{user_id}/habilitar` accesible solo para roles `proctor` y `admin`. Al recibir la habilitación, el sistema SHALL cambiar el estado de la solicitud a `habilitado_por_proctor`, registrar quién habilitó y cuándo, y a partir de ese momento el gate SHALL permitir al alumno rendir SIN biometría.

#### Scenario: Proctor habilita solicitud pendiente exitosamente
- **WHEN** un proctor autenticado llama `POST /api/v1/consent/alternative/{user_id}/habilitar` con `{ "exam_id": "<id>" }`
- **THEN** el sistema transiciona el estado a `habilitado_por_proctor`
- **THEN** la respuesta incluye `estado: "habilitado_por_proctor"`, `habilitado_por: "<proctor_id>"`, `timestamp_habilitacion: "<iso>"`

#### Scenario: Gate permite rendir al alumno habilitado por proctor (sin biometría)
- **WHEN** `puedeRendir()` se evalúa para un alumno con solicitud en estado `habilitado_por_proctor`
- **THEN** el sistema retorna `{ puede: true }`
- **THEN** el alumno puede iniciar el examen sin pasar por el flujo de biometría
- **THEN** `biometria_habilitada()` retorna `false` (la verificación fue humana, no biométrica)

#### Scenario: Habilitación con rol insuficiente es rechazada
- **WHEN** un alumno o usuario sin rol `proctor`/`admin` llama al endpoint de habilitación
- **THEN** el sistema retorna `403 Forbidden`

#### Scenario: Habilitación de solicitud inexistente retorna error
- **WHEN** el proctor intenta habilitar a un alumno que no tiene solicitud pendiente
- **THEN** el sistema retorna `404 Not Found` con detalle apropiado

### Requirement: Proctor puede listar solicitudes de vía alternativa pendientes
El sistema SHALL proveer `GET /api/v1/consent/alternative/pendientes` que retorne todas las solicitudes con estado `pendiente_proctor`. Solo accesible para roles `proctor` y `admin`. La respuesta SHALL incluir `user_id`, `exam_id`, `timestamp_solicitud` por cada solicitud.

#### Scenario: Lista de pendientes con solicitudes activas
- **WHEN** un proctor llama `GET /api/v1/consent/alternative/pendientes`
- **THEN** el sistema retorna la lista de solicitudes con estado `pendiente_proctor`
- **THEN** cada entrada incluye `user_id`, `exam_id`, `timestamp_solicitud`

#### Scenario: Lista vacía cuando no hay pendientes
- **WHEN** no existe ninguna solicitud con estado `pendiente_proctor`
- **THEN** el sistema retorna una lista vacía `[]` con status 200

#### Scenario: Acceso denegado a rol sin permisos
- **WHEN** un alumno llama `GET /api/v1/consent/alternative/pendientes`
- **THEN** el sistema retorna `403 Forbidden`

### Requirement: Eliminar el bypass de biometría por vía alternativa en el gate frontend
El sistema SHALL eliminar la lógica `via_alternativa === true → biometriaVigente = true` del frontend (`api.ts`). El perfil de un alumno con solicitud de vía alternativa SHALL permanecer `perfil_completo = false` mientras el estado sea `pendiente_proctor`. Solo cuando el estado sea `habilitado_por_proctor` el gate SHALL marcar el perfil como completo (sin biometría pero con verificación humana).

#### Scenario: Vía alternativa pendiente no marca perfil como completo
- **WHEN** un alumno tiene solicitud con estado `pendiente_proctor`
- **THEN** `recalcularPerfilCompleto()` retorna `perfil_completo: false`
- **THEN** `puedeRendir()` retorna `{ puede: false, codigo: "via_alternativa_pendiente" }`

#### Scenario: Vía alternativa habilitada marca perfil como completo sin biometría
- **WHEN** un alumno tiene solicitud con estado `habilitado_por_proctor`
- **THEN** `recalcularPerfilCompleto()` retorna `perfil_completo: true`
- **THEN** `puedeRendir()` retorna `{ puede: true }`
- **THEN** `biometriaVigente` es `true` (derivado de la habilitación humana), pero sin captura biométrica real
