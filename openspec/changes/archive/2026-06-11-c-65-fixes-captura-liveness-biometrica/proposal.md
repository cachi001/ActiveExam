## Why

La captura de referencia biométrica (liveness enrollment) ya está implementada (linaje C-22 / C-34 / C-36 / C-54 / C-62), pero tiene bugs que **degradan la confianza del liveness** y la experiencia del alumno: las advertencias de encuadre (poca luz, dos rostros, lejos/cerca) **no frenan la captura**, así que un alumno puede "adivinar" los gestos moviéndose sin cumplir las condiciones; los gestos se aceptan **al instante** (umbral por frames, no por tiempo) y a veces se saltan dos pasos de golpe; el anillo de progreso del óvalo se **pinta rotado 90°** y no coincide con el rostro; la cámara se ve oscura sin que el sistema pida mejor exposición; y falta el **feedback sonoro de fallo** (solo suena el acierto). Ninguno toca la cadena de custodia, pero juntos debilitan la señal de liveness y la usabilidad del enrollment, que es la base de toda verificación 1:1 posterior.

## What Changes

- **Las advertencias de encuadre BLOQUEAN la evaluación de gestos** mientras estén activas (sin rostro, múltiples rostros, poca luz, mucha luz, lejos, cerca). Hoy el `framingHint` solo cambia color y suena un beep, pero la máquina de retos sigue evaluando. Se gatea la evaluación con el mismo patrón que el `cooldownActiveRef` existente. (`descentrado` queda como hint no bloqueante.)
- **Confirmación de gesto por TIEMPO, no por frames.** El umbral pasa de "N frames consecutivos" (atado a 30–60 fps ⇒ 50–130 ms) a "gesto sostenido ≥ umbral en milisegundos" (configurable, ~500 ms), independiente del framerate. Se refuerza el gate de neutralidad para impedir que el residuo del reto anterior confirme el siguiente (el "dos pasos de golpe").
- **El anillo de progreso del óvalo se renderiza alineado** con la guía y con el rostro. Se elimina el `transform="rotate(-90 …)"` aplicado a una elipse (válido solo para círculos; en una elipse intercambia los ejes y la deja apaisada).
- **Exposición real de cámara, sin tocar el frame guardado.** La captura solicita mejor exposición al sensor vía `applyConstraints` (best-effort, con fallback si el dispositivo no lo soporta) y mantiene la guía "poca luz". El frame que se persiste para el embedding/evidencia **se sigue tomando del video crudo, sin post-proceso** (regla dura #6).
- **Sonido de fallo.** Se agrega `playError()` al catálogo de `sounds.ts` y se dispara en los fallos relevantes (timeout de baseline sin éxito, liveness pasivo fallido, cámara virtual detectada, error de captura). El acierto ya suena.
- **Re-captura/renovación con límite suave + auditoría.** El botón ya existe (incluido "Rehacer captura" estando vigente). Se le agrega un límite suave (cooldown/contador de re-capturas) y un registro en el audit log; la referencia anterior se conserva versionada. La renovación nunca auto-sanciona ni invalida una rendición en curso (L2.5).

## Capabilities

### New Capabilities
- `biometric-capture-framing-gate`: las advertencias de encuadre bloqueantes pausan la evaluación de retos de liveness hasta que el encuadre se normaliza; define qué hints son bloqueantes y cómo se reanuda.
- `biometric-gesture-hold-timing`: la confirmación de cada gesto es por tiempo sostenido (umbral en ms, independiente del framerate) y se garantiza el avance de a lo sumo un reto por gesto (anti doble-paso).
- `biometric-capture-exposure`: la captura solicita exposición real al sensor (best-effort vía constraints) y nunca post-procesa el frame de referencia persistido.
- `biometric-capture-av-feedback`: feedback audiovisual de la captura — sonido de fallo además del de acierto, y renderizado correcto (alineado) del anillo de progreso del óvalo.
- `biometric-recapture-rate-limit`: la re-captura/renovación de la referencia se permite con un límite suave y queda registrada en el audit log, conservando la referencia anterior.

### Modified Capabilities
- `biometric-liveness-active`: la evaluación secuencial de retos en el loop RAF de `BiometricCapture.tsx` queda subordinada (a) al gate de encuadre y (b) al umbral de confirmación por tiempo. Cambia el comportamiento de aceptación de gestos descripto en esta capability, sin tocar el liveness pasivo ni la detección de cámara virtual.

## Impact

- **Frontend (client-side, MediaPipe):**
  - `frontend/src/ui/biometric/CaptureOval.tsx` — quitar la rotación del `<ellipse>` de progreso.
  - `frontend/src/ui/BiometricCapture.tsx` — gate de encuadre antes de evaluar retos; hold por tiempo; `applyConstraints` de exposición; disparo de `playError()`.
  - `frontend/src/vision/enrollmentChallengeDetector.ts` — umbrales de confirmación por tiempo (o helper de hold temporal) en reemplazo/complemento de `FRAMES_MIN_*`.
  - `frontend/src/ui/biometric/framingGuide.ts` — marcar qué hints son bloqueantes vs informativos.
  - `frontend/src/ui/biometric/sounds.ts` — nuevo `playError()`.
  - `frontend/src/screens/enrollment/BiometricRenewalStatus.tsx` y el flujo que invoca la renovación — límite suave de re-captura.
- **Backend (mínimo, solo #6):** registro en audit log de cada re-captura/renovación (quién, cuándo, origen) y conservación versionada de la referencia anterior. Reusa la cadena de custodia existente (re-inferencia + firma server-side); no se agrega persistencia nueva de embedding.
- **Sin impacto en:** cadena de custodia criptográfica, cómputo del embedding, cifrado at-rest, ni el liveness pasivo / detección de cámara virtual (se preservan).
- **Reglas duras:** #5 (L2.5, nunca sanción automática), #6 (cliente = sensor no confiable; el frame persistido no se post-procesa), #7 (embedding = dato sensible, Ley 25.326).
