## Context

El flujo de liveness activo en el enrollment y la verificación biométrica tiene tres defectos estructurales que se combinan para que el primer reto siempre pase solo:

1. **Evaluación paralela**: `BiometricCapture.tsx` evalúa TODOS los retos pendientes en cada frame con un `for (const id of currentDesafios)`. El primero que cruza el umbral gana, independientemente del orden.
2. **Umbrales absolutos permisivos**: `SMILE_WIDTH_THRESHOLD=0.10` y `FACE_APPROACH_THRESHOLD=0.48` son valores que la cara en reposo natural de la mayoría de los usuarios ya satisface. El umbral de parpadeo (`BLINK_CLOSE_THRESHOLD=0.018`) es muy estrecho (ojo muy cerrado) pero `FRAMES_MIN_BLINK=1` significa que un solo frame lo activa.
3. **Sin cooldown ni confirmación deliberada**: cuando un reto se resuelve, el siguiente se habilita instantáneamente sin transición perceptible.

El reto "acercarse" (`FACE_APPROACH_THRESHOLD=0.48`) es adicionalamente frágil: el umbral varía enormemente con la distancia inicial del alumno a la cámara, y "acercarse" no es un gesto de liveness estándar en contexto bancario o de proctoring (no distingue un video pregrabado de cerca).

**Stack afectado**: 100 % frontend. Los archivos clave son `liveness.ts`, `enrollmentChallengeDetector.ts`, `BiometricCapture.tsx`, y los presentacionales `CaptureProgress.tsx` / `CaptureOverlay.tsx`. El backend recibe el callback `onComplete` existente sin cambio de firma.

**Changes relacionados**:
- C-09 (biometria-liveness): introdujo el catálogo inicial de retos.
- C-34 (biometria-perfil-funcional): reemplazó liveness mock por evaluación real con RAF loop.
- C-36 (verificacion-biometrica-inmersiva): refactorizó a `BiometricCapture` compartido.
- C-49 (cablear-codigo-fantasma): cabló liveness pasivo y retos resueltos reales al callback.
- C-53 (vision-mesh-objetos): agregó Face Mesh 468 landmarks opt-in y face_count.

## Goals / Non-Goals

**Goals:**
- Retos evaluados en secuencia estricta uno a la vez (máquina de estados `idle → baseline → challenge[N] → cooldown → done`).
- Evaluación por delta relativo al baseline neutral del propio alumno, eliminando los falsos positivos en reposo.
- Sostenimiento mínimo de frames elevado (≥3 blink, ≥4 giro/sonrisa) para evitar activación por frames espurios.
- Cooldown corto (≥400 ms) entre confirmación de un reto y habilitación del siguiente.
- Feedback visual deliberado: "Paso N ✓ completado" visible antes de transitar al siguiente reto.
- Catálogo de retos reducido a `[parpadear, girar_cabeza, sonreír]` (orden **aleatorio** por intento, barajado con Fisher-Yates al iniciar la captura).
- El reto `girar_cabeza` pide una **dirección específica** elegida al azar por intento (izquierda o derecha); la instrucción en pantalla indica la dirección concreta.
- Frame de referencia para el embedding computado durante la fase baseline (cara frontal estable), no sobre el último frame del loop.

**Non-Goals:**
- Cambios en el backend o en la firma de `onComplete`.
- Cambios en la detección pasiva de liveness (ventana deslizante de 15 frames — ya funciona).
- Cambios en la detección de cámara virtual.
- Implementar liveness Fase 2 (modelo pasivo server-side — es scope de un change futuro, DD-18).
- Soporte para retos personalizables por el llamador (el catálogo es fijo; el orden y la dirección de giro se aleatorizan internamente).
- Modo fallback manual: se mantiene tal cual (ya funciona, y en fallback la evaluación automática no corre).

## Decisions

### D-1: Máquina de estados secuencial en lugar del loop paralelo

**Decisión**: reemplazar el `for (const id of currentDesafios)` en el loop RAF de `BiometricCapture.tsx` por una máquina de estados con `challengeIndexRef` que apunta al reto activo. Solo se evalúa el reto en `desafios[challengeIndexRef.current]`.

**Alternativa descartada A**: mantener el loop paralelo pero con cooldown. Requeriría cooldown por reto y lógica de "cuál fue el primero" — más complejo y no elimina el problema de fondo (múltiples retos activos en el mismo frame).

**Alternativa descartada B**: evaluar todos en paralelo pero bloquear los siguientes en la UI. Rompe el propósito: el reto puede resolverse silenciosamente en background incluso si no se muestra.

**Justificación**: la secuencialidad estricta es la experiencia de referencia (apps de banco). Solo hay UN reto activo en cada momento; la máquina de estados garantiza orden y simplifica el código.

### D-2: Delta relativo al baseline neutral (evaluación adaptiva)

**Decisión**: agregar una fase `baseline` al inicio de la captura. Durante los primeros ~12-15 frames con cara detectada y estable (varianza de nariz < umbral, esperando al frame 10+ para evitar subexposición inicial — OQ-3), capturar:
- `baselineBlinkOpenness`: apertura vertical media del ojo izquierdo (landmarks[159].y − landmarks[145].y) en el baseline.
- `baselineSmileWidth`: ancho de boca medio (|landmarks[291].x − landmarks[61].x|) en el baseline.
- `baselineGazeX`: gaze.x medio (referencia de frente).

Los umbrales de evaluación dejan de ser absolutos y pasan a ser relativos:
- **Parpadear**: `openness < baselineBlinkOpenness * BLINK_RELATIVE_FACTOR` (ej: factor=0.45 → el ojo debe cerrarse al menos al 45 % de su apertura en reposo).
- **Sonreír**: `smileWidth > baselineSmileWidth * SMILE_RELATIVE_FACTOR` (ej: factor=1.25 → la boca debe abrirse al menos un 25 % más que en reposo).
- **Girar**: sin cambio (el giro ya es relativo a la posición del iris; el umbral GAZE_TURN_THRESHOLD se ajusta de 0.18 a 0.22 para mayor robustez).

**Alternativa descartada**: subir los umbrales absolutos. Resolvería algunos falsos positivos pero no todos (el baseline varía según el usuario, el hardware y la iluminación). No escala.

**Justificación**: el mismo enfoque que usa Face ID / app de banco: mide el CAMBIO sobre el estado inicial del usuario, no un valor absoluto global.

### D-3: Frame de referencia para embedding durante la fase baseline

**Decisión**: en la fase `baseline`, cuando se acumulan suficientes frames estables, capturar el frame actual del `<video>` como `bestReferenceFrameRef`. Este frame se usa en `procesarCompletado()` en lugar del último frame arbitrario del loop.

**Justificación**: el embedding de referencia debe computarse sobre una cara frontal y neutral. El último frame del loop puede ser del alumno en plena sonrisa o giro — no es representativo.

### D-4: Catálogo de retos `[parpadear, girar_cabeza, sonreír]` con orden aleatorio y giro direccional aleatorio

**Decisión**: eliminar `acercarse` del catálogo. El reto `girar_cabeza` pide una **dirección específica** elegida al azar en cada intento ("Girá la cabeza a la DERECHA" o "a la IZQUIERDA") y solo acepta el giro hacia esa dirección. El **orden** de los 3 retos se baraja con Fisher-Yates (`Math.random()`) al iniciar la captura; la máquina de estados sigue siendo secuencial (un reto activo por vez), pero la secuencia varía entre intentos.

La convención de signo del código existente se respeta:
- Dirección "IZQUIERDA" (lo que el usuario percibe en espejo) → `gaze.x > +GAZE_TURN_THRESHOLD`
- Dirección "DERECHA" (lo que el usuario percibe en espejo) → `gaze.x < -GAZE_TURN_THRESHOLD`

El baseline neutral siempre se captura ANTES del primer reto, independientemente del orden barajado.

**Alternativa descartada**: orden fijo `parpadear → girar_cabeza → sonreír`. Un orden fijo y un giro que acepta cualquier dirección es vulnerable a replay con video pregrabado; el estándar challenge-response bancario exige que la secuencia y la dirección sean impredecibles para el atacante.

**Justificación**: orden aleatorio + dirección de giro aleatoria es la best practice anti-replay de liveness activo (apps bancarias, ISO/IEC 30107-3 PAD). Impide pre-grabar la respuesta porque tanto el orden como la dirección cambian en cada intento. El baseline siempre precede al primer reto, lo que mantiene el invariante de la fase baseline. `Math.random()` es aceptable en este contexto client-side de liveness (no requiere CSPRNG).

### D-5: Cooldown visual entre pasos

**Decisión**: al resolver un reto, entrar en un estado `cooldown` de **350 ms** antes de avanzar al siguiente índice. Durante el cooldown se muestra "Paso N ✓" con un checkmark verde. El RAF sigue corriendo pero no evalúa ningún reto.

**Justificación**: el cooldown hace el flujo perceptible y deliberado (experiencia de banco). Sin él, el step change es instantáneo y confuso. 350 ms es suficiente para la confirmación visual sin alargar innecesariamente el flujo; las apps bancarias reales usan 300-500 ms.

### D-6: `FRAMES_MIN` elevados y sostenimiento por reto

**Decisión**:
- `FRAMES_MIN_BLINK`: 1 → **3** (parpadeo requiere sostener el ojo cerrado ~100 ms a 30fps; suficiente para eliminar falsos positivos sin alargar el gesto natural).
- `FRAMES_MIN_TURN`: 2 → **4** (giro requiere sostener ~133 ms).
- `FRAMES_MIN_SMILE`: 2 → **4** (sonrisa requiere sostener ~133 ms).
- El acumulador se resetea si el reto activo deja de cumplirse en el frame siguiente (ya funciona así hoy).

**Justificación**: el sostenimiento mínimo era demasiado bajo (1 frame = 33 ms). Con 3 frames para parpadeo y 4 para los demás, el falso positivo por ruido es prácticamente cero, y el flujo total (baseline ~12-15 frames + 3 retos + 2 cooldowns de 350 ms) se mantiene en el objetivo de **~5-7 segundos**.

## Risks / Trade-offs

- **[Riesgo: baseline lento en iluminación pobre]** → Si el alumno está en un entorno mal iluminado, la cara puede tardar más en estabilizarse (varianza alta de landmarks). Mitigación: límite máximo de frames para el baseline (si después de 60 frames no estabiliza, usar los últimos 10 como baseline aunque sean ruidosos). Además, el feedback "Encuadrá tu rostro..." ya orienta al alumno.
- **[Riesgo: baseline incorrecto si el alumno ya está sonriendo al entrar]** → El baseline captura la sonrisa como neutral, y el reto de sonreír nunca se satisface. Mitigación: instrucción explícita en la pantalla previa ("Mirá al frente con expresión neutral") y un check de validez del baseline (smileWidth del baseline no puede superar un techo absoluto de 0.14).
- **[Riesgo: usuario gira en la dirección equivocada]** → Con el giro direccional, el usuario podría girar hacia el lado incorrecto. Mitigación: la instrucción en pantalla indica explícitamente la dirección ("a la DERECHA" / "a la IZQUIERDA") con indicador visual (flecha). Si el usuario gira en la dirección opuesta, el acumulador no avanza; la instrucción permanece en pantalla hasta que gire en la dirección correcta.
- **[Trade-off: tiempo de captura ágil]** → El objetivo es **~5-7 segundos** totales (baseline ~12-15 frames a 30fps ≈ 0.4-0.5 s de estabilización, + 3 retos × ~0.1-0.13 s, + 2 cooldowns × 350 ms = ~1.5-2 s adicionales). Esto es deliberado y perceptible como en banca, pero sin fricción excesiva (las apps bancarias apuntan exactamente a este rango).
- **[Trade-off: compatibilidad con el catálogo del backend]** → El backend tiene `acercarse` en su catálogo de retos. Al eliminarlo del frontend, los `retosResueltos` que se envían en `onComplete` nunca incluirán `acercarse`. El backend debe ser tolerante a no recibirlo (ya lo es hoy porque los retos son opcionales en la re-inferencia). Verificar en la implementación.

## Migration Plan

1. Actualizar `liveness.ts`: nuevo catálogo `SEQUENTIAL_CHALLENGES`, nuevo tipo `SequentialChallengeState`, nuevo tipo `TurnDirection = 'izquierda' | 'derecha'`.
2. Actualizar `enrollmentChallengeDetector.ts`: nueva función `evaluateChallengeRelative()` que recibe el baseline y, para `girar_cabeza`, la `turnDirection` aleatoria; mantener `evaluateChallenge()` como deprecated (por si se usa en otros contextos).
3. Actualizar `BiometricCapture.tsx`: agregar refs `challengeIndexRef`, `cooldownRef`, `baselineRef`, `bestReferenceFrameRef`, `turnDirectionRef` (dirección de giro elegida al azar); barajar `SEQUENTIAL_CHALLENGES` con Fisher-Yates al montar; reemplazar el loop paralelo por la máquina de estados.
4. Actualizar `CaptureProgress.tsx`: agregar prop `cooldownActivo` para mostrar el estado de confirmación del paso; agregar prop `turnDirection` para mostrar la instrucción direccional del reto de giro.
5. Actualizar `CaptureOverlay.tsx`: pasar `cooldownActivo` y `turnDirection` al `CaptureProgress`.
6. Verificar que `EnrollmentBiometricStep.tsx` y `Biometria.tsx` (si existe) no rompen con el nuevo flujo — la firma de `onComplete` no cambia.

No hay rollback de datos ni migración de DB. El change es puro frontend, sin estado persistido que pueda quedar inconsistente.

## Open Questions

- **OQ-1**: ¿El backend tolera `retosResueltos` sin `acercarse`? Verificar en `api.ts` / mock antes de implementar la tarea de integración.
- **OQ-2**: ¿El catálogo de retos del backend (`app.domain.biometrics.liveness`) necesita actualizarse para eliminar `acercarse`? El comment en `liveness.ts` dice que espeja el dominio del backend. Coordinar con el change de backend si corresponde (fuera del scope de C-54).
- **OQ-3**: ¿El `<video>` frame capturado como `bestReferenceFrameRef` durante el baseline es de calidad suficiente para `computeFaceDescriptor()`? Si la cámara aún está ajustando la exposición en los primeros frames, el frame puede estar subexpuesto. Mitigación: esperar al frame 10+ para el baseline (no el primero).
