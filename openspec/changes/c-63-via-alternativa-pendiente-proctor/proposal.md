## Why

La "vía alternativa" del consentimiento (RN-CO-05) es hoy un bypass silencioso: el alumno que elige no dar biometría queda inmediatamente marcado como `perfil_completo = true` en el gate del frontend (`api.ts:165`) y puede rendir sin ninguna verificación humana real. El toast "Tu caso se escala a un proctor" miente — no se registra ningún estado pendiente, el proctor no recibe nada procesable, y el alumno navega directo a `/sala-espera`. Esto rompe el Artículo 3 de la Ley 25.326 (tratamiento sin base legal válida), la regla de dominio #5 (decisión disciplinaria siempre humana) y el propio propósito de RN-CO-05.

## What Changes

- **REMOVE bypass de gate**: eliminar la línea `e.consentimiento?.via_alternativa === true ||` que fuerza `biometriaVigente = true` en `api.ts:165`. Con vía alternativa el perfil queda `pendiente`, NO completo.
- **ADD estado `pendiente_verificacion_alternativa`**: nuevo estado persistido cuando el alumno elige vía alternativa (campo `estado` en la solicitud, no en el acuse de consentimiento que es inmutable). El alumno con ese estado no puede rendir hasta que un proctor lo habilite manualmente.
- **ADD endpoint de habilitación**: `POST /api/v1/consent/alternative/{user_id}/habilitar` (auth proctor/admin) que transiciona el estado a `habilitado_por_proctor`. Endpoint auxiliar `GET /api/v1/consent/alternative/pendientes` para que el proctor vea la cola mínima.
- **MODIFY `Consent.tsx` y `EnrollmentConsentStep.tsx`**: al elegir vía alternativa, llamar al endpoint real, no navegar a `/sala-espera`. Mostrar pantalla de espera "Tu solicitud quedó registrada. Un proctor verificará tu identidad." con el botón Rendir deshabilitado.
- **MODIFY gate `puedeRendir`** (frontend + backend): el código `via_alternativa_pendiente` bloquea con mensaje claro. El código `via_alternativa_habilitada` (habilitado por proctor) permite rendir sin biometría.
- **ADD badge en Mis Exámenes**: "Verificación alternativa pendiente" cuando el alumno tiene estado pendiente.
- **NO BREAKING**: el flujo normal (aceptar + biometría) no se modifica. El alumno habilitado por proctor puede rendir sin biometría (ese es el punto), pero solo después de la acción humana.

## Capabilities

### New Capabilities
- `alternative-verification-pending`: Gestión del ciclo de vida de la solicitud de vía alternativa — estados (pendiente / habilitado), persistencia, gate de rendir, endpoints de proctor y badge de estado en el alumno.

### Modified Capabilities
- `exam-enrollment`: El gate `puedeRendir` debe reconocer los nuevos códigos `via_alternativa_pendiente` y `via_alternativa_habilitada` y mostrar mensajes de bloqueo/avance apropiados. La pantalla "Mis exámenes" suma el badge de estado alternativo.

## Impact

- `frontend/src/lib/api.ts` — eliminar bypass línea 165; añadir método `solicitarViaAlternativa()` y `estadoViaAlternativa()`; actualizar `puedeRendir` con nuevos códigos; mocks de los nuevos endpoints.
- `frontend/src/screens/Consent.tsx` — reemplazar `alternativa()` (toast + navigate) por llamada real + pantalla de espera.
- `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx` — `handleViaAlternativa` registra solicitud real y muestra estado pendiente.
- `backend/app/presentation/api/v1/consent/router.py` — nuevos endpoints `POST /alternative/{user_id}/habilitar` y `GET /alternative/pendientes`.
- `backend/app/application/consent/service.py` — métodos `registrar_solicitud_alternativa`, `habilitar_alternativa`, `listar_pendientes`.
- `backend/app/domain/entities/` — nueva entidad `SolicitudViaAlternativa` con campos `user_id`, `exam_id`, `estado`, `timestamp_solicitud`, `timestamp_habilitacion`, `habilitado_por`.
- `backend/app/infrastructure/persistence/` — modelo ORM + migración Alembic para `solicitudes_via_alternativa`.
- `backend/app/domain/consent_flow/rules.py` — `ResolucionConsentimiento` extiende con `VIA_ALTERNATIVA_PENDIENTE` y `VIA_ALTERNATIVA_HABILITADA`; `evaluar_gate` diferencia ambos estados.
- Tests (módulo slim, postgres:16-alpine): tests de persistencia, gate y endpoints.
