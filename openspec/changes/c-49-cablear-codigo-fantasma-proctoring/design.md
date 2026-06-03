## Context

La plataforma de proctoring L2.5 tiene una brecha crítica: módulos de seguridad (buffer de eventos, liveness pasivo, detección de cámara virtual) están implementados y testeados en `frontend/src/transport/` y `frontend/src/vision/liveness.ts` pero **nunca se instancian en el flujo de producción**. El resultado observable es:

1. `store.scorePropio` siempre queda en 0 → `Cierre.tsx` muestra riesgo 0 a todo alumno.
2. Si la red cae durante el examen, todos los eventos del período se pierden sin posibilidad de replay.
3. `liveness_ok` se manda como `true` hardcodeado a `api.enviarBiometriaProctoring` → cualquier alumno supera el liveness.
4. `retos_resueltos: []` hardcodeado → el backend nunca sabe qué retos resolvió el alumno.
5. El payload del evento no lleva hash del screenshot → la primera capa de cadena de custodia del cliente está vacía.

Este change no crea lógica nueva: conecta lo existente.

## Goals / Non-Goals

**Goals:**
- Cablear `CircularEventBuffer` + `IndexedDbEventBufferStore` en `useExamProctoring.ts` con listeners `online`/`offline` para drain automático al recuperar red.
- Cablear `addScore(delta)` en el callback de evento para que `store.scorePropio` acumule.
- Cablear `derivePassiveSignals()` + `passivePassed()` + `detectVirtualCamera()` en el loop RAF de `BiometricCapture.tsx` usando un acumulador de ventana deslizante (~15 frames).
- Propagar `liveness_ok` real (no hardcodeado) y `retos_resueltos` reales a `Biometria.tsx` vía firma ampliada de `onComplete`.
- Incluir `screenshot_sha256_cliente` en el payload del evento calculado con `hashClip` de `clipCustody.ts`.

**Non-Goals:**
- **Firma HMAC de eventos** (`eventSignature.ts`, `firmarClip`): el backend slim **no valida la firma** del payload del evento. No existe una `sessionKey` rotativa en este entorno (nace del flujo biométrico completo, no implementado en el slim). Firmar client-side sin validación server-side es **teatro de seguridad** — crea la ilusión de protección sin ningún valor real. Se documenta como deuda técnica: cablear cuando el backend implemente la validación.
- **Cadena de custodia completa** (`EvidenceCadenceController`, presigned PUT, `EvidenceNotification`): requiere:
  - Endpoint `/evidence/presign` inexistente en el backend slim.
  - Storage externo (MinIO / S3 con Object Lock) no configurado en el entorno actual.
  - `sessionKey` rotativa post-verificación biométrica.
  Cablear estas piezas sin el backend listo generaría errores de red que romperían el flujo. Se documenta como deuda técnica para cuando se implemente el backend completo de evidencia (C-12/C-24).
- Cambios en el backend slim.
- Re-escritura de `ResilientStudentEventChannel` completo (acoplado a WebSocket, que el slim no tiene; se extrae solo buffer + drain con adaptador REST).
- Calibración definitiva de umbrales de liveness pasivo (se usa umbral conservador con flag de calibración).

## Decisions

### D1 — Buffer + drain con adaptador REST, no con ResilientStudentEventChannel completo

`ResilientStudentEventChannel` asume un `StudentEventChannel` (WebSocket) que el backend slim no tiene. Usarlo completo requeriría un `channelFactory` mock que haría el sistema opaco.

**Decisión**: instanciar `CircularEventBuffer(new IndexedDbEventBufferStore())` directamente en `useExamProctoring.ts`. Crear un `ReplaySender` adaptador inline (~30 líneas) que llame a `api.enviarEventoProctoring(sessionId, event)` como el mecanismo de reenvío.

**Patrón buffer-first con purga-en-éxito (CRÍTICO)**: el ciclo por evento es `append(id, payload)` ANTES del POST → ejecutar el POST → **si el POST resuelve OK, `confirm(id)` para PURGAR el evento del buffer** → si el POST rechaza (red caída), NO confirmar (queda pendiente para el drain). `drainAndReplay` se invoca al evento `online` y solo reenvía lo que quedó pendiente (lo que falló).

**Por qué el `confirm(id)` on-success es obligatorio**: `CircularEventBuffer.confirm()` (eventBuffer.ts:76) es la ÚNICA vía de purga del buffer. Si se omite y solo se purga dentro del drain, el buffer retiene TODOS los eventos del examen y `drainAndReplay` los reenvía en bloque en la primera reconexión. Como el backend slim NO deduplica por `event_id`, eso reinserta el examen completo duplicado — no es el "duplicado raro" de R2, es duplicación masiva. El `replayCoordinator.ts:13` asume explícitamente que "la autoridad de deduplicación es el backend", supuesto que NO se cumple en el slim; por eso el cliente debe purgar agresivamente en éxito.

**Alternativa descartada**: instanciar `ResilientStudentEventChannel` completo → requiere channelFactory WebSocket inexistente en el slim; añadiría >200 líneas de boilerplate sin beneficio.

### D2 — Acumulador de ventana deslizante para liveness pasivo

`derivePassiveSignals()` espera métricas agregadas (`blinkVariance`, `motionVariance`, `depthRange`). El loop RAF entrega un frame por vez.

**Decisión**: mantener un `ref` de ventana circular de los últimos N=15 frames en `BiometricCapture.tsx`. En cada frame:
- `blinkVariance`: varianza de la apertura vertical del ojo izquierdo `(landmarks[159].y - landmarks[145].y)` y ojo derecho `(landmarks[386].y - landmarks[374].y)` entre frames de la ventana.
- `motionVariance`: varianza de la posición `(x, y)` del centroide de nariz (landmark 1) entre frames.
- `depthRange`: `max(z) - min(z)` de todos los z del frame actual sobre todos los frames de la ventana.

Umbral conservador: se usan los valores actuales de `liveness.ts` (`blinkVariance > 0.01`, `motionVariance > 0.0005`, `depthRange > 0.02`) sin modificarlos. Ver Riesgo R1.

**Alternativa descartada**: calcular métricas solo sobre el frame actual → sin ventana temporal, `blinkVariance` siempre 0 (una sola muestra no tiene varianza).

### D3 — Firma ampliada de onComplete

`BiometricCapture.onComplete` actual: `(landmarks, frame)`. Necesitamos propagar `passiveOk`, `retosResueltos`, `virtualCameraDetected` a `Biometria.tsx`.

**Decisión**: ampliar la firma a `(landmarks, frame, passiveOk: boolean, retosResueltos: string[], virtualCameraDetected: boolean)`. Impacta dos callers: `Biometria.tsx` (verificación) y el caller de enrollment (perfil). El caller de enrollment ignora los campos nuevos con `_` o los usa para registrar datos adicionales — sin breaking change semántico; sí es un cambio de firma TypeScript.

**Alternativa descartada**: un objeto de resultado `{ landmarks, frame, biometricResult }` → más limpio, pero requiere refactor mayor de la interfaz `BiometricCaptureProps`; se postula como mejora futura.

### D4b — detectVirtualCamera: solo señal, no escala en vivo (decisión del usuario)

La cámara virtual detectada se propaga al backend pero **NO desvía el flujo**: el alumno avanza al examen y la revisión humana decide (L2.5 puro, consistente con el resto del sistema). Dos deudas técnicas asumidas:
1. **No escala a proctor en vivo**: un spoofing por cámara virtual no interrumpe la sesión; queda como señal para revisión asíncrona.
2. **String mágico en `resultado`**: hoy se propaga vía `resultado: 'camara_virtual_detectada'` (sobreescribe `'verificado'`) porque el tipo de `api.enviarBiometriaProctoring` no tiene campo propio. Limpiar a un campo explícito (`virtual_camera_detected: boolean`) cuando se toque el backend de biometría.

### D4 — detectVirtualCamera con canvas 16×12 de pixel variance

La varianza de píxeles entre frames se calcula sobre un canvas reducido para no bloquear el hilo principal.

**Decisión**: en cada frame, dibujar el bitmap en un canvas `16×12` off-screen y calcular la media cuadrática de la diferencia de píxeles con el frame anterior (escala de grises). `frameRateJitter` se deriva de `performance.now()` entre frames; `faceCountStability` es la proporción de frames con exactly 1 cara en la ventana.

### D5 — SHA-256 del screenshot en payload del evento

`hashClip` de `clipCustody.ts` acepta `ArrayBuffer`. `captureVideoFrame` devuelve base64 string. Se convierte a `ArrayBuffer` vía `Uint8Array(atob(b64))` antes de hashear.

**Decisión**: calcular el hash ANTES de la llamada a `api.enviarEventoProctoring` y agregar `screenshot_sha256_cliente` al payload. Si el screenshot es null, el campo se omite del payload (no se envía undefined).

**Por qué es valioso aunque el backend lo ignore hoy**: el campo queda persistido en la tabla de eventos del slim. Cuando el backend implemente re-hash server-side, puede verificar retrospectivamente los eventos del cambio anterior (o al menos desde que se deploye este change).

### D6 — Comportamiento del liveness en fallback manual

Cuando el motor falla y el usuario completa los retos en modo manual (`fallbackManual: true`), `passiveOk` debe ser `false` explícito (no hay métricas de landmarks). `virtualCameraDetected` debe ser `false` (no hay píxeles que analizar). `retos_resueltos` se propaga igual desde `resueltosRef`.

**Decisión**: en `procesarCompletado()`, si el flag `fallbackManual` es `true`, llamar `onComplete(landmarks, frame, false, resueltosRef.current, false)`. Esto informa honestamente al backend que el liveness pasivo no pudo evaluarse.

## Risks / Trade-offs

**R1 — Umbrales de liveness mal calibrados bloquean alumnos legítimos** (RIESGO CRÍTICO)

Los umbrales en `liveness.ts` (`blinkVariance > 0.01`, etc.) se definieron teóricamente. Con condiciones reales de iluminación baja, cámara de baja resolución o personas con movilidad reducida, los umbrales pueden rechazar alumnos legítimos.

→ **Mitigación**: (a) los umbrales actuales son conservadores (bajos) — se aceptan pequeñas varianzas; (b) agregar en `BiometricCapture.tsx` un contador de frames con liveness en false: si supera 90 frames (~3 segundos de RAF a 30fps) sin pasar, no se bloquea el flujo sino que se registra `passiveOk: false` y se propaga al backend para revisión humana (L2.5, no sanción automática); (c) task explícita de validación con capturas reales antes de release a producción.

**R2 — Duplicados en replay del buffer**

El backend slim no deduplica por `event_id`. Con el patrón buffer-first + purga-en-éxito (ver D1), el buffer solo retiene los eventos que el POST NO logró confirmar. El único caso de duplicado residual es el clásico de redes: la red cae después de que el POST llegó al backend pero antes de que el cliente recibiera el 200 → el evento se persistió server-side pero el cliente no lo purgó, y lo reenvía en el drain.

→ **Mitigación aceptada hoy**: ese duplicado residual se persiste 2× con la misma data. El proctor ve el evento dos veces en la cola de revisión — es ruido, no corrupción. Se documenta como mejora futura del backend (idempotencia por `event_id`).

→ **Lo que NO es aceptable y este diseño previene**: omitir el `confirm(id)` on-success convertiría cada reconexión en una reinyección del examen completo (ver D1). El `confirm` on-success es obligatorio, no opcional.

**R3 — IndexedDB no disponible (modo privado / iOS Safari)**

`IndexedDbEventBufferStore` puede fallar al abrir la base en algunos entornos.

→ **Mitigación**: envolver la instanciación del buffer en try/catch; en fallback, operar sin buffer (comportamiento actual). El examen continúa degradado pero sin errores.

**R4 — Firma ampliada de onComplete impacta enrollment**

El caller de enrollment en `/perfil` (o donde se monte `BiometricCapture` para enrollment) necesita actualizar su handler `onComplete` para aceptar los 3 parámetros nuevos. Si no se actualiza, TypeScript lo detecta en compilación (no es riesgo silencioso).

→ **Mitigación**: el check de TypeScript captura todos los callers no actualizados. La task incluye actualizar ambos callers explícitamente.

**R5 — Performance del acumulador de ventana en dispositivos lentos**

Calcular varianzas sobre 15 frames en cada iteración RAF puede ser costoso en hardware de gama baja.

→ **Mitigación**: las operaciones son O(N) sobre N=15 valores escalares — costo negligible vs. la inferencia MediaPipe que ya ocurre en el mismo loop.

## Migration Plan

1. Implementar los cambios en ramas feature por bloque (Bloque 1, Bloque 2, Bloque 3).
2. Ejecutar suite de tests existente (`vitest`) — los módulos de transport y liveness tienen cobertura completa; no se modifican, solo se invocan.
3. Validación manual: (a) simular corte de red durante examen → verificar replay del buffer, (b) verificar `store.scorePropio > 0` al detectar un evento, (c) verificar liveness pasivo con iluminación baja y alta para detectar falsos negativos antes de release.
4. Rollback: cada cambio es aditivo/correctivo en archivos separados — revertir un archivo no afecta los otros bloques.

## Open Questions

- **Calibración de umbrales de liveness** (R1): ¿cuál es el dataset de captura real disponible para validar `blinkVariance > 0.01` y `motionVariance > 0.0005`? Esto debe resolverse antes del release a producción de Bloque 2.
- **Enrollment caller** (RESUELTO): el caller de enrollment es `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` (monta `BiometricCapture` en su fase `capturando`, `onComplete` en línea ~118). El segundo caller es `Biometria.tsx` (verificación). Ambos deben actualizar su `onComplete` a la firma de 5 parámetros; el de enrollment ignora `passiveOk`/`virtualCameraDetected` (su liveness se evalúa en la captura de referencia, no condiciona el guardado). El cambio es no-breaking en runtime, solo de tipo TypeScript.
- **Binding de identidad oficial** (fuera de alcance de c-49, candidato a change propio): la referencia biométrica se calcula de la captura con retos (`EnrollmentBiometricStep`), NO de la foto de perfil (`imagen: null` en `guardarReferenciaBiometrica`) ni del DNI. La verificación 1:1 garantiza consistencia ("misma persona que se enroló") pero no ancla la identidad a un documento oficial (C-39 análisis de DNI nunca implementado; foto institucional de referencia de C-07/SU-01 no cableada). Es una decisión de seguridad pendiente, no un bug de este change.
