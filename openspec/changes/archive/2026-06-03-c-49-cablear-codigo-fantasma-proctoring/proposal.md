## Why

Una auditoría del código fuente detectó que múltiples módulos de seguridad y resiliencia están escritos, testeados e importados, pero **nunca instanciados en el flujo de producción** ("código fantasma"): el buffer IndexedDB nunca se conecta al canal REST, el score propio del alumno siempre queda en 0, el liveness pasivo real nunca se evalúa (está hardcodeado `true`), y los retos biométricos resueltos nunca se propagan al backend. Este change enchufa lo existente sin crear features nuevas — cerrar la brecha entre lo que el código promete y lo que realmente ejecuta.

## What Changes

- **Buffer IndexedDB + drain en reconexión** (`useExamProctoring.ts`): instanciar `CircularEventBuffer` + `IndexedDbEventBufferStore` y un `ReplaySender` adaptador (~30 líneas) que envuelve `api.enviarEventoProctoring`. Agregar listeners `online`/`offline` para disparar el drain del buffer al recuperar red. Los duplicados en replay se persisten 2× (aceptable; mejora futura del backend).
- **scorePropio wired** (`useExamProctoring.ts`): llamar `addScore(delta)` del store Zustand en el callback de evento. Hoy `store.scorePropio` queda permanentemente en 0 y `Cierre.tsx` muestra 0.
- **Liveness pasivo real** (`BiometricCapture.tsx`): invocar `derivePassiveSignals()` + `passivePassed()` en el loop RAF con acumulador de ventana deslizante (~15 frames). Calcular `blinkVariance` (landmarks 159/145/386/374), `motionVariance` (centroide nariz landmark 1), `depthRange` (max–min z). Propagar el resultado real a `liveness_ok` en `Biometria.tsx` — HOY está hardcodeado `true`.
- **detectVirtualCamera() wired** (`BiometricCapture.tsx`): invocar en el loop con métricas calculadas (`frameRateJitter`, `faceCountStability`, pixel variance sobre canvas 16×12). Si detecta feed estático → propagar `virtualCameraDetected: true` al callback.
- **retos_resueltos reales** (`BiometricCapture.tsx` + `Biometria.tsx`): propagarlos desde `resueltosRef` via la firma ampliada de `onComplete`. Hoy `Biometria.tsx` manda `retos_resueltos: []` hardcodeado.
- **Hash SHA-256 cliente en payload de evento** (`useExamProctoring.ts`): calcular `SHA-256` del screenshot antes del POST usando `hashClip` de `frontend/src/features/biometria/clipCustody.ts` y agregarlo al payload como `screenshot_sha256_cliente`. Primera capa de cadena de custodia desde el cliente; el backend lo ignora hoy pero queda registrado.

**Fuera de alcance (deuda técnica documentada):**
- Firma HMAC de eventos: no cablear — el backend slim no valida firma y no hay `sessionKey` rotativa en este entorno; sería teatro de seguridad.
- Cadena de custodia completa (`EvidenceCadenceController`, presigned PUT, `EvidenceNotification`): requiere storage externo + endpoint `/evidence/presign` inexistente en el slim.

## Capabilities

### New Capabilities

- `exam-proctoring-resilience`: resiliencia de red con buffer IndexedDB + drain on reconnect + scorePropio wired en el flujo de examen del alumno.
- `biometric-liveness-active`: liveness pasivo real (varianza de parpadeo, micro-movimientos, profundidad 3D), detección de cámara virtual y propagación real de retos resueltos en el flujo biométrico.
- `client-custody-hash`: hash SHA-256 del screenshot en el payload del evento como primera capa de cadena de custodia del cliente.

### Modified Capabilities

- `exam-enrollment`: la firma de `onComplete` en `BiometricCapture` se amplía para incluir `passiveOk`, `retosResueltos` y `virtualCameraDetected` — afecta a todos los callers (enrollment + verificación).

## Impact

- `frontend/src/proctoring/useExamProctoring.ts` — instanciar buffer, drain, scorePropio, SHA-256 en payload.
- `frontend/src/ui/BiometricCapture.tsx` — acumulador pasivo, detectVirtualCamera, firma onComplete ampliada.
- `frontend/src/screens/Biometria.tsx` — consumir liveness_ok real y retos_resueltos reales.
- `frontend/src/transport/` — leer interfaces (CircularEventBuffer, IndexedDbEventBufferStore, drainAndReplay, ReplaySender); no modificar.
- `frontend/src/vision/liveness.ts` — invocar derivePassiveSignals, passivePassed, detectVirtualCamera; no modificar.
- `frontend/src/features/biometria/clipCustody.ts` — invocar hashClip; no modificar.
- `frontend/src/lib/store.ts` — invocar addScore; no modificar.
- Sin cambios en backend slim ni en otros callers fuera del scope descrito (enrollment enrollment-engine-loader, etc. — solo lectura de interfaces existentes).
