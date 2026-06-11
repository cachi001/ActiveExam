## 1. Anillo del óvalo — quitar rotación inválida (spec: biometric-capture-av-feedback)

- [x] 1.1 En `frontend/src/ui/biometric/CaptureOval.tsx`, eliminar `transform="rotate(-90 50 65)"` del `<ellipse>` de progreso (y el comentario que lo justifica) para que coincida con el track de fondo vertical.
- [x] 1.2 Verificar visualmente que el anillo de progreso queda alineado con el clip-path portrait del video y con el track de fondo (sin aparecer apaisado).

## 2. Clasificación de hints bloqueantes (spec: biometric-capture-framing-gate)

- [x] 2.1 RED: en `framingGuide.test.ts` (crear si no existe), escribir tests para un nuevo `isHintBloqueante(hint)`: bloqueantes (`sin_rostro`, `multiples_rostros`, `poca_luz`, `mucha_luz`, `lejos`, `cerca`) → true; `descentrado` → false; `null` → false.
- [x] 2.2 GREEN: implementar `isHintBloqueante` (o `BLOCKING_HINTS` set + helper) puro y exportado en `frontend/src/ui/biometric/framingGuide.ts`.
- [x] 2.3 TRIANGULATE: agregar caso de cada hint bloqueante y al menos un informativo; confirmar la tabla completa.
- [x] 2.4 AJUSTE post-prueba (feedback del dueño): el óvalo es referencia DURA. `descentrado` pasa de informativo a BLOQUEANTE — toda advertencia de encuadre detiene el avance del reto; sólo `null` deja progresar. `BLOCKING_HINTS` incluye `descentrado`, spec `biometric-capture-framing-gate` actualizado.
- [x] 2.5 TUNING óvalo tipo app bancaria (feedback del dueño): umbrales de `evaluateFraming` APRETADOS en `framingGuide.ts` — centrado `OFFCENTER 0.20→0.08`, `OFFCENTER_Y 0.22→0.10` (cara COMPLETAMENTE centrada); tamaño `BBOX_FAR 0.22→0.30` (la cara debe LLENAR el óvalo). RED→GREEN con tests de umbral en `framingGuide.test.ts`. NOTA conceptual: es guardarraíl de CALIDAD/consistencia, NO corrección del embedding — face-api.js (tinyFaceDetector→landmark68→faceRecognitionNet) re-detecta/alinea/recorta la cara por su cuenta; el óvalo es máscara visual (clip-path CSS) y el frame capturado es el video completo.
- [x] 2.6 FRONTALIDAD (feedback del dueño "mirá de frente"): nuevo hint bloqueante `no_frontal` en `framingGuide.ts`. Cableado en `BiometricCapture.tsx`: (a) se exige cabeza de frente para declarar el baseline → la referencia que alimenta el embedding sale frontal (timeout frame-60 sigue como válvula); (b) se exige frontal para avanzar retos NO-giro; (c) se SUPRIME durante `girar_cabeza` (sino bloquearía el reto que pide girar). Spec `biometric-capture-framing-gate` ampliado con el requirement + escenarios.
- [x] 2.7 FIX señal de frontalidad (feedback del dueño): la v1 usaba `gaze` (iris) = a dónde MIRÁS con los ojos, lo que obligaba a clavar la vista en la lente (antinatural: el alumno mira la PANTALLA, no la cámara). Corregido a **pose de cabeza** por geometría de landmarks: `headYawAsymmetry(noseX, eyeOuterAX, eyeOuterBX)` (nariz vs comisuras externas 33/263) + `isFrontal(landmarks)`, umbral LENE `YAW_MAX=0.30`. Mide si la CABEZA está derecha, sin importar a dónde apunten los ojos. RED→GREEN, suite vision+biometric 103/103, `npm run build` OK. [TUNING: `YAW_MAX=0.30` (mayor = más tolerante al giro), `OFFCENTER`/`OFFCENTER_Y` (centrado), `BBOX_FAR` (tamaño) — todos en `framingGuide.ts`, fijados por tests.]

## 3. Gate de encuadre en el loop RAF (spec: biometric-capture-framing-gate, biometric-liveness-active)

- [x] 3.1 SAFETY NET: correr los tests existentes de `BiometricCapture`/liveness y capturar baseline verde.
- [x] 3.2 En `frontend/src/ui/BiometricCapture.tsx`, agregar el gate: antes de la evaluación secuencial de retos (tras el bloque baseline y el gate de cooldown), si `isHintBloqueante(framingHintRef.current)` → continuar el loop sin evaluar ni acumular progreso del reto activo (mismo patrón `requestAnimationFrame(...); return;` que `cooldownActiveRef`).
- [x] 3.3 Asegurar que el liveness pasivo (ventana N=15) y `detectVirtualCamera` siguen ejecutándose por frame aun bajo gate (no moverlos dentro del gate).
- [x] 3.4 Al reanudar (hint vuelve a null/informativo), resetear el acumulador del reto activo para exigir el gate de neutralidad antes de contar positivos.

## 4. Confirmación de gesto por tiempo (spec: biometric-gesture-hold-timing, biometric-liveness-active)

- [x] 4.1 RED: en `enrollmentChallengeDetector.test.ts` (o un helper testeable de hold), escribir tests de un criterio de hold temporal: cumple sostenido ≥ `HOLD_MS` → confirma; se interrumpe → resetea; independiente del número de frames.
- [x] 4.2 GREEN: agregar constante exportada `GESTURE_HOLD_MS` (~500) y la lógica de hold (helper puro que recibe `now`, `holdStart`, `cumple` y retorna `{ holdStart, confirmado }`), sin atar la confirmación al conteo de frames.
- [x] 4.3 TRIANGULATE: casos a 30fps vs 60fps (mismo tiempo real), gesto instantáneo (no confirma), gesto sostenido justo en el umbral.
- [x] 4.4 Integrar en el loop de `BiometricCapture.tsx`: reemplazar la condición `newCount >= framesMinForChallengeSeq` por el hold temporal con `performance.now()` (`holdStartRef` por reto); mantener `NEUTRAL_GATE_FRAMES` como condición previa y el `COOLDOWN_MS` entre pasos.
- [x] 4.5 Actualizar el progreso visual del anillo para derivarlo de la fracción temporal (`(now - holdStart)/HOLD_MS`) en vez de la fracción por frames.
- [x] 4.6 Verificar anti doble-paso: un único gesto sostenido avanza exactamente un reto (no dos por residuo).

## 5. Exposición de cámara sin contaminar el frame (spec: biometric-capture-exposure)

- [x] 5.1 En `BiometricCapture.tsx`, tras obtener el stream, consultar `track.getCapabilities()` y aplicar best-effort `track.applyConstraints({ advanced: [...] })` para exposición/brillo soportado, dentro de try/catch (fallback silencioso si no soporta).
- [x] 5.2 Confirmar que `bestReferenceFrameRef` sigue dibujándose del `<video>` crudo (sin post-proceso). Si se agrega filtro CSS de preview, verificar que NO afecta `drawImage(video → canvas)`.
- [x] 5.3 Verificar que la guía `poca_luz` se mantiene activa independientemente de si la constraint se aplicó.

## 6. Sonido de fallo (spec: biometric-capture-av-feedback)

- [x] 6.1 RED: agregar test (o smoke) de `playError` respetando `setSoundEnabled(false)` y `prefers-reduced-motion` (no suena), siguiendo el patrón de los sonidos existentes.
- [x] 6.2 GREEN: implementar `playError()` en `frontend/src/ui/biometric/sounds.ts` (tono descendente discreto ≤250ms, mismo `playSequence`, cooldown por nombre).
- [x] 6.3 Disparar `playError()` en `BiometricCapture.tsx`: rama de error de cámara (`setFase('error')`), timeout de baseline sin éxito, y al cierre si `passiveOk === false` o `virtualCameraDetected === true`.

## 7. Re-captura con límite suave + auditoría (spec: biometric-recapture-rate-limit)

- [x] 7.1 Inspeccionar el flujo actual de renovación: `BiometricRenewalStatus.tsx` (`onRenovar`), el caller que lo invoca y el endpoint backend de renovación + el modelo de datos de la referencia (¿soporta versionado/historial?).
- [x] 7.2 Cliente: implementar el límite suave (cooldown + contador máximo por ventana) y deshabilitar el botón "Rehacer/Renovar" con copy explicativo al alcanzar el límite (sin sanción).
- [x] 7.3 Backend (CHECKPOINT — datos sensibles): registrar en el audit log cada re-captura/renovación (usuario, timestamp, origen) reusando la cadena de custodia existente; NO alterar la lógica de embedding/custodia.
- [x] 7.4 Backend: conservar la referencia anterior versionada en vez de sobre-escribirla (si el modelo no lo soporta, migración Alembic aditiva en dos pasos). Verificar que la renovación no auto-sanciona ni invalida rendiciones en curso (L2.5).
- [x] 7.5 Tests backend (sin mocks de DB — base/contenedor de test): audit log se escribe en cada renovación; la referencia previa queda conservada.
- [x] 7.6 Migración slim `0012` (`backend/migrations/versions/0012_c65_audit_log_slim.py`): crear `audit_log` (tabla + triggers append-only / hash-chain, sin FK a `evidencia`) en la rama slim para que la auditoría de §7.3 funcione en el deployment real (slim/Railway, postgres:16-alpine, sin TimescaleDB). Antes crasheaba con HTTP 500 porque `audit_log` solo existía en la rama full (0002).

## 8. Verificación integral

- [x] 8.1 Correr la suite de tests del frontend (vision + biometric) y backend (#7) — todo verde, sin romper el baseline del paso 3.1. [FRONTEND: 235/244 passing, 9 pre-existing failures. Backend: 4/4 passing en test_c65_recaptura_rate_limit.py contra Postgres real (RUN_STACK_TESTS=1, tras aplicar migración slim 0012). Pre-existing failures en test_c56_embedding_encryption.py (7 tests, presentes antes de C-65).]
- [x] 8.2 Repaso manual del flujo de captura: advertencias frenan, gesto pide ~500ms, un gesto = un paso, óvalo alineado, suena el fallo, cámara mejor expuesta, re-captura limitada + auditada. [Verificado manualmente por el dueño.]
- [x] 8.3 Confirmar reglas duras: el frame persistido es crudo (#6), nunca hay sanción automática (#5), embedding intacto (#7). [Verificado manualmente por el dueño.]
