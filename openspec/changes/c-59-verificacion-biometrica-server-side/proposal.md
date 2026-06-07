## Why

En producción (modo real) un alumno que YA tiene su biometría cargada NO puede rendir: tras el consentimiento, la pantalla de verificación dice "no se encontró datos biométricos" y bloquea el flujo. La causa es un cableado a medio terminar: la verificación 1:1 hoy es **stateless** (el cliente debe mandar el embedding de referencia), pero por privacidad (Ley 25.326) ese embedding **no viaja al cliente** en modo real — se persiste cifrado en el backend y el cliente solo retiene un `referencia_id` opaco. El gate del frontend exige el embedding de referencia local, que es `null` por diseño, así que siempre cae en "no_enrolado". La verificación server-side quedó sin cablear: anda solo en demo (donde el embedding vive en el navegador).

Es un bug **bloqueante** de producción: ningún alumno con embedding cifrado en la DB puede pasar la verificación biométrica.

## What Changes

- **Nuevo endpoint backend stateful y autenticado** (`POST /api/v1/proctoring/biometria/verificar-referencia`): recibe `{embedding_vivo, umbral?}` + Bearer JWT. Con la identidad del JWT (`sub`) busca el `embedding_referencia` VIGENTE del usuario, lo **descifra server-side** (reusando `EmbeddingEncryptionService` de C-56), compara con `comparar_identidad` y devuelve `{distancia, es_match, umbral}`. NUNCA devuelve ni loguea el embedding. Si el usuario no tiene referencia vigente → `404` (distinto de "match fallido").
- **Nuevo endpoint backend de estado de referencia** (`GET /api/v1/proctoring/biometria/referencia/estado`): autenticado, devuelve `{tiene_referencia_vigente: bool}` para que el frontend decida el gate `no_enrolado` en modo real sin exponer el embedding.
- **Montaje en `main_slim.py`**: el sub-router de biometría pasa a recibir el `session_factory`, el `embedding_encryption` y el guard de auth desde el app state, manteniendo el endpoint stateless actual intacto (retrocompat/demo).
- **Recableado del frontend** (`Biometria.tsx` + `api.ts`): en **modo real** captura el embedding vivo y llama al endpoint stateful (el backend identifica por JWT; no se manda el embedding de referencia); el gate `no_enrolado` se basa en `GET .../referencia/estado`, no en `biometriaReferencia` local. En **modo demo** se mantiene el flujo client-side actual (embedding de referencia en el navegador). Las dos ramas quedan documentadas explícitamente.
- El endpoint stateless `POST /biometria/verificar` se **conserva** (retrocompat/demo); se documenta como demo-only.

## Capabilities

### New Capabilities
- `biometric-verification-server-side`: verificación de identidad biométrica 1:1 ejecutada server-side, identificando al usuario por su JWT y descifrando el embedding de referencia vigente en el backend, sin exponerlo nunca al cliente ni a los logs. Incluye la consulta de estado de referencia para el gate del frontend.

### Modified Capabilities
<!-- Sin cambios de requisitos a nivel spec en capabilities existentes. El endpoint stateless previo se conserva sin modificar su contrato. -->

## Impact

- **Backend**:
  - `app/presentation/api/v1/proctoring/biometria/router.py` — nuevos endpoints stateful + estado; el endpoint stateless se conserva.
  - `app/presentation/api/v1/proctoring/biometria/schemas.py` — nuevos schemas `VerificarReferenciaIn`, `VerificarReferenciaOut`, `EstadoReferenciaOut` (todos `extra='forbid'`).
  - `app/presentation/api/v1/proctoring/router.py` y `app/main_slim.py` — el factory del router de biometría recibe `embedding_encryption` y el guard de auth desde el state.
  - Reuso: `EmbeddingEncryptionService.decrypt` (C-56), `EmbeddingReferenciaRepository.obtener_vigente` (C-56), `comparar_identidad` (matching), `require_roles(Rol.ESTUDIANTE)` (auth).
- **Frontend**:
  - `frontend/src/lib/api.ts` — nueva rama real en `verificarBiometria` (o nuevo método `verificarBiometriaReferencia`) + nuevo `estadoReferenciaBiometrica`.
  - `frontend/src/screens/Biometria.tsx` — gate `no_enrolado` basado en estado del backend (real) vs `biometriaReferencia` (demo).
- **Privacidad / Ley 25.326 (regla dura #7)**: el embedding de referencia sigue sin salir crudo al cliente; el descifrado y la comparación ocurren server-side (regla dura #6 — cliente = sensor no confiable).
- **Tests**: backend con Postgres real (sin mocks de DB, sin TimescaleDB) — enrollment cifrado → verificar-referencia cercano (`es_match=true`) / lejano (`es_match=false`) / sin referencia (`404`).
- **Sin migraciones nuevas**: reusa la tabla `embedding_referencia` (0007/0008).
- **Sin breaking changes**: el contrato stateless previo y el flujo demo quedan intactos.
