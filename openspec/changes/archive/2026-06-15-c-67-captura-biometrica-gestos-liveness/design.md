# Design — C-67 `captura-biometrica-gestos-liveness`

## Gobernanza (LEER PRIMERO — dominio CRÍTICO)

Este change toca **biometría + anti-spoofing**, el dominio más sensible del sistema (datos biométricos = dato sensible bajo Ley 25.326; el liveness es la primera capa de defensa de identidad). Por el modelo de gobernanza por dominio (JR Stack Stage 4), aplica el nivel **CRÍTICO**:

- **La implementación de este change requiere aprobación humana explícita ANTES de escribir cualquier línea de código.** Esta propuesta no implementa nada; es solo análisis + contrato (proposal + specs + tasks). El paso `/opsx:apply` no debe arrancar sin confirmación del dueño del producto.
- **El sistema permanece L2.5 (regla dura #5)**: nunca sanciona automáticamente. La comparación 1:1 que ve el alumno **prioriza/informa, no emite veredicto**. La decisión disciplinaria es **siempre humana** (revisión asíncrona). El endurecimiento anti-foto sube el costo del fraude, no automatiza un castigo.
- **Cliente = sensor no confiable (regla dura #6)**: la comparación coseno mostrada en el navegador es **UX de conveniencia**. La verificación **autoritativa** es la re-inferencia server-side (c-12 / c-59). El frame de referencia que alimenta el embedding **no se post-procesa** (se toma del video crudo).
- **Embedding = dato sensible (regla dura #7, Ley 25.326)**: el vector de 128-d nunca se loguea ni se muestra. La pantalla de resultado del examen muestra "coincide / no coincide" y, como mucho, valores numéricos opacos (distancia/umbral) detrás de un detalle opcional — nunca el vector.

## Context

El flujo biométrico client-side tiene tres piezas vivas:

1. **Captura de referencia** (`EnrollmentBiometricStep.tsx` → `BiometricCapture.tsx`): máquina de estados secuencial (idle → baseline → challenge[N] → cooldown → done, C-54) con baseline neutral, evaluación por delta relativo (`enrollmentChallengeDetector.ts`), confirmación de gesto por **tiempo sostenido** (`gestureHold`, `GESTURE_HOLD_MS=500`, C-65), gate de encuadre (C-65), liveness pasivo de ventana N=15 y detección de cámara virtual. El frame del baseline alimenta el descriptor 128-d (`faceEmbedding.ts`).
2. **Anillo de progreso** (`CaptureOval.tsx`): un `<ellipse>` SVG superpuesto con `strokeDasharray/strokeDashoffset`. Hoy está **dentro** del óvalo (radios `RX-2`/`RY-2`, sobre la imagen), con trazo grueso (2.6). El progreso (`progreso` 0..1) se calcula en `BiometricCapture` como `(retosCompletos + fracReto) / total`, donde `fracReto = (now - holdStart) / GESTURE_HOLD_MS` y `holdStart` **se borra al perder el gesto** ⇒ el relleno del reto activo se reinicia a cero.
3. **Verificación 1:1 del examen** (`Biometria.tsx`): captura el embedding vivo, lo compara (server-side en modo real vía c-59; client-side en demo), y al `es_match` avanza con `setTimeout(navigate('/sala-espera'), 1400)` mostrando "Distancia 0.31 < umbral 0.35" — jerga, y sin que el alumno confirme nada.

El dueño quiere: sonrisa precisa y rápida; progreso en el borde exterior, fino, con relleno verde y reanudación sin reinicio; cues de audio de progreso/pérdida; resultado del examen en lenguaje claro con gate de confirmación; y anti-foto robusto.

## Goals / Non-Goals

**Goals**
- Anillo de progreso en el **borde exterior** del óvalo, fino, con relleno verde tipo barra de carga circular.
- Progreso que **reanuda sin reiniciar** cuando el gesto se recupera.
- Cues de audio: progreso del gesto y pérdida del gesto.
- Sonrisa más precisa (métrica de landmarks) y más rápida (latencia propia).
- Pantalla de resultado del examen en español cotidiano, sin jerga, con gate de "continuar".
- Defensa anti-foto consolidada (reto-respuesta + pasivo + cámara virtual, ISO 30107-3) reportada al backend.

**Non-Goals**
- NO cambiar la cadena de custodia, el cómputo/persistencia del embedding ni el cifrado at-rest.
- NO cambiar el contrato server-side de verificación (c-59) ni mover la decisión autoritativa al cliente.
- NO automatizar ninguna sanción (L2.5 intacto).
- NO agregar un modelo PAD pasivo server-side (eso es Fase 2, DD-18); este change consolida lo client-side existente.
- NO post-procesar el frame de referencia para "mejorar" la foto.

## Decisions

### D1 — Relleno circular incremental en el borde EXTERIOR (arco SVG, progreso persistido, reanudar sin reinicio)

**Qué.** El anillo de progreso se reubica del interior al **borde exterior** del recorte del video y el relleno verde avanza de forma incremental y reanudable.

- **Borde exterior**: en `CaptureOval.tsx`, el `<ellipse>` de progreso se dibuja con radios **mayores** que el recorte del video (p. ej. `RX`/`RY` plenos o `RX+δ`, en lugar de `RX-2`/`RY-2`), de modo que el trazo quede en el contorno externo del óvalo y no sobre la cara. El `clipPath: ellipse(50% 50%)` del video se mantiene; el SVG vive en una capa superior con su propio `viewBox`.
- **Arco por `stroke-dashoffset`**: se conserva la técnica actual (`strokeDasharray = PERIMETER`, `strokeDashoffset = PERIMETER * (1 - progreso)`), que ya dibuja un arco que crece desde 0 hasta el perímetro completo. El color del trazo vira a verde (`#22c55e`) durante el llenado del gesto activo (no solo en éxito), comunicando "barra de carga".
- **Progreso persistido / reanudación sin reinicio**: el problema actual es que `fracReto` depende de `holdStart`, que `gestureHold` borra en cuanto el gesto se pierde. La solución es **acumular tiempo efectivo de gesto cumplido** en un acumulador por reto (`gestureAccumMs`) que NO se borra al perder el gesto:
  - mientras el gesto se cumple, `gestureAccumMs += dt` (dt = delta de `performance.now()` entre frames cumplidos);
  - cuando el gesto se pierde, `gestureAccumMs` **se conserva** (solo se oculta el relleno activo / se baja el tono);
  - cuando el gesto se reanuda, sigue sumando desde el valor guardado;
  - el reto se confirma cuando `gestureAccumMs >= GESTURE_HOLD_MS`;
  - `fracReto = min(1, gestureAccumMs / GESTURE_HOLD_MS)`.
  Esto desacopla el progreso visual del `holdStart` instantáneo. El gate de neutralidad y el anti doble-paso (C-65) se preservan: el acumulador solo corre tras pasar el gate de neutralidad y se reinicia al confirmar el reto y al pasar a otro reto.

**Por qué.** `stroke-dashoffset` sobre el `<ellipse>` ya existente es el cambio mínimo y frame-rate independiente. Acumular tiempo efectivo (en vez de leer `now - holdStart`) es la forma natural de "continuar desde donde quedó" sin reescribir la máquina de hold.

**Alternativas consideradas.** (a) Canvas 2D `arc()` por frame — rechazado: reintroduce dibujo imperativo y no reusa el SVG declarativo existente. (b) Mantener `holdStart` pero no resetearlo al perder el gesto — rechazado: rompería la semántica de `gestureHold` (que sí debe resetear el hold de confirmación temporal); separar "confirmación temporal" de "progreso acumulado" es más limpio. (c) Dos óvalos concéntricos (uno track, uno fill) en divs — rechazado: el SVG ya soporta track + fill como dos `<ellipse>`.

### D2 — Señales auditivas de progreso (WebAudio tick de progreso + cue de pérdida)

**Qué.** Se agregan al catálogo de `sounds.ts` dos funciones nuevas:
- `playGestureProgress()` — un "tick" breve y agudo que se dispara periódicamente mientras el gesto progresa correctamente (por ejemplo, al cruzar fracciones del relleno, no por frame, para no saturar). Reusa el cooldown por nombre (`SAME_SOUND_COOLDOWN_MS`) para no estallar en bucle.
- `playGestureLost()` — un cue grave y corto cuando el gesto se pierde y el relleno se oculta (distinto del `playError()` de fallo terminal y del `playHint()` de encuadre).

Ambos respetan `prefers-reduced-motion`, `setSoundEnabled(false)` y el cooldown, igual que el resto del catálogo. Se disparan desde `BiometricCapture` en las transiciones de progreso (cruce de umbral de fracción) y de pérdida (`cumple` pasa de true a false con `gestureAccumMs > 0`).

**Por qué.** El WebAudio sintetizado en runtime ya es el patrón del proyecto (sin assets, sin red, sin licencias). Disparar por **cruce de fracción** (no por frame) evita el zumbido continuo y da la sensación de "barra que carga".

**Alternativas.** Tono continuo modulado por el progreso — rechazado: más intrusivo y más difícil de respetar el cooldown/reduced-motion; un tick discreto es suficiente.

### D3 — Sonrisa más precisa y más rápida (métrica de landmarks + latencia propia)

**Qué.** Hoy la sonrisa es `smileWidth = |lm[291].x - lm[61].x|` (ancho entre comisuras) evaluado contra `baseline.smileWidth * 1.25`. El ancho de boca varía poco al sonreír y es ruidoso; por eso "tarda en dar OK". Se mejora la métrica:
- incorporar la **elevación de las comisuras** relativa al baseline: al sonreír, las comisuras (61, 291) suben respecto a un punto de referencia estable del labio/centro de boca (p. ej. el punto medio del labio superior 0/13 o la nariz 1). Una métrica compuesta `smileScore = wWidth·Δancho + wRaise·Δelevación` relativa al baseline distingue mejor la sonrisa del reposo.
- afinar el umbral relativo para esta métrica compuesta (validado con los tests existentes de `enrollmentChallengeDetector.test.ts`, sin reabrir el auto-OK en reposo que C-54/C-59 cerraron).
- **latencia propia de la sonrisa**: permitir un `GESTURE_HOLD_MS` por reto (o un factor) menor para la sonrisa, de modo que confirme más rápido una vez detectada, manteniendo el gate de neutralidad. El baseline de sonrisa sigue validándose con `isBaselineSmileValid` (no aceptar baseline con el alumno ya sonriendo).

**Por qué.** El ancho de boca solo es una señal pobre; sumar elevación de comisuras (un eje ortogonal) sube la separación señal/ruido sin cambiar el modelo (siguen siendo landmarks de Face Mesh). Latencia propia evita penalizar a la sonrisa con el mismo hold que parpadeo/giro.

**Alternativas.** Clasificador de expresión de face-api (`faceExpressionNet`) — rechazado para este change: agrega un modelo/peso y latencia de inferencia extra; la métrica geométrica relativa es suficiente y coherente con el resto del detector.

### D4 — Defensa anti-foto (PAD): reto-respuesta activo + señales pasivas + cámara virtual (ISO/IEC 30107-3)

**Qué.** Se consolida (no se reinventa) la defensa combinada para que **una foto no pase**:
- **Activo (reto-respuesta)**: los 3 gestos secuenciales barajados (`parpadear`, `girar_cabeza` con dirección aleatoria, `sonreír`) — una foto estática no puede ejecutarlos. El orden y la dirección aleatorios suben el costo de un video pregrabado.
- **Pasivo**: `derivePassiveSignals` exige parpadeo (varianza de apertura), micro-movimientos (varianza de nariz) y **profundidad 3D coherente** (rango de z de los 468 landmarks). Una foto plana da varianza ~0 y z ~0 ⇒ `passivePassed=false`.
- **Cámara virtual / inyección**: `detectVirtualCamera` (varianza de píxeles inter-frame, jitter de framerate, estabilidad perfecta de face_count) reporta inyección de pipeline.
- **Estándar**: ISO/IEC 30107-3 (APCER/BPCER). El objetivo de este change es Nivel 1–2 (fotos, videos de reproducción, máscaras de mediana sofisticación) en la capa cliente. El **límite honesto** (DD-18): ningún liveness en navegador es inmune a inyección/deepfake puppet-master; por eso la red de seguridad real es **re-inferencia server-side + verificación continua + revisión humana**.
- El intento reporta al backend `liveness_ok` (pasivo real), `retos_resueltos` (reales) y la señal de cámara virtual — ya cableado (C-49). Este change endurece la **redacción de contrato** (specs) y la consistencia, no agrega un endpoint nuevo.

**Por qué.** El paradigma cliente no puede garantizar inmunidad; la defensa correcta es **capas combinadas + autoridad server-side**. Declararlo explícito en specs evita prometer lo que el cliente no puede cumplir.

**Alternativas.** Modelo PAD pasivo open-source server-side (Silent-Face-Anti-Spoofing) — es **Fase 2 (DD-18)**, fuera de alcance; se deja como Open Question.

### D5 — Pantalla de resultado de la verificación del examen en lenguaje claro (gate de "continuar")

**Qué.** Tras la comparación 1:1 (`Biometria.tsx`), el flujo **se detiene** en una pantalla de resultado que el alumno debe reconocer antes de continuar:
- **Coincide**: mensaje claro tipo "Listo, confirmamos que sos vos. Ya podés entrar a tu examen." con un botón **explícito** "Continuar al examen" (reemplaza el `setTimeout(navigate, 1400)` automático).
- **No coincide**: "No pudimos confirmar que seas vos en esta toma." + opciones de reintentar / escalar a una persona (las que ya existen), explicado sin jerga.
- **Lenguaje claro / sin jerga (regla dura de UI)**: el copy principal NO contiene "embedding", "coseno", "umbral", "descriptor", "1:1", "distancia". Los valores numéricos (distancia/umbral) se mueven a un **detalle opcional** ("Ver detalle técnico") o a un tooltip de glosario (`term-tooltip-component` / `Term`), nunca como texto principal. Se mantiene la frase de que "ninguna decisión la toma una máquina; siempre la revisa una persona" (L2.5, ya presente en enrollment).
- **Gate**: el examen no avanza hasta que el alumno presiona "Continuar" (en caso de match). Esto cumple el pedido "que pare, lo muestre y lo deje ver antes de continuar".

**Por qué.** El alumno tiene derecho a entender la decisión que lo habilita (transparencia, espíritu de la Ley 25.326). El gate explícito reemplaza el avance automático que "pasa demasiado rápido".

**Alternativas.** Mostrar el resultado como toast efímero — rechazado: no garantiza que el alumno lo vea ni lo entienda; el pedido es explícito de "detener y dejar ver".

## Risks / Trade-offs

- **[Riesgo] Afinar la sonrisa reabre el auto-OK en reposo (falso positivo de C-54/C-59).** → Mitigación: la métrica compuesta sigue siendo **relativa al baseline**; los tests de `enrollmentChallengeDetector.test.ts` cubren el caso "cara neutral no confirma sonrisa"; agregar casos de triangulación (sonrisa real vs reposo vs boca abierta sin sonreír).
- **[Riesgo] Los cues de audio resultan molestos o se disparan en bucle.** → Mitigación: cooldown por nombre ya existente + disparo por cruce de fracción (no por frame) + respeto de `prefers-reduced-motion` y `setSoundEnabled(false)`.
- **[Riesgo] Reubicar el anillo al borde exterior desalinea con el recorte del video en distintos aspect ratios.** → Mitigación: el SVG usa el mismo `viewBox`/`preserveAspectRatio` que el contenedor del óvalo; test de render que verifica que track y fill comparten orientación y radios; revisión visual en mobile/desktop.
- **[Riesgo] El alumno percibe la pantalla de resultado como fricción extra.** → Mitigación: en match, un solo botón claro; copy breve y positivo. El trade-off (un click extra) es aceptable frente a la transparencia ganada.
- **[Riesgo / honestidad] Prometer "ni una foto pasa" puede leerse como inmunidad total.** → Mitigación: las specs declaran el alcance (ISO Nivel 1–2 en cliente) y el límite (inyección/deepfake requieren autoridad server-side + humano). No se promete inmunidad absoluta.
- **[Trade-off] Acumular `gestureAccumMs` desacopla progreso visual de confirmación temporal.** → Se acepta: son dos preocupaciones distintas (UX de progreso vs criterio de confirmación); el reto se confirma por el acumulador, manteniendo independencia de framerate.

## Migration Plan

No hay migración de datos ni de contrato. Es 100% client-side y aditivo:
- Los componentes (`CaptureOval`, `BiometricCapture`, `sounds`, `enrollmentChallengeDetector`, `Biometria`) se modifican preservando sus firmas públicas (`onComplete` intacto).
- La pantalla de resultado del examen es un estado nuevo dentro de `Biometria.tsx`; no cambia rutas ni API.
- Sin migraciones Alembic, sin cambios de endpoints. Rollback = revertir el commit del frontend.

## Open Questions

### Resueltas (decisión del dueño, 2026-06-13)
1. **Ritmo / latencia de la sonrisa** → El dueño pidió que **TODO sea deliberado, NO rápido** ("lo recomendado, que sea lento y no tan rápido todo"). Se **ANULA la aceleración** de D3: la sonrisa mantiene un hold deliberado (mismo orden que los demás gestos, ~500 ms **o más**; nunca menor). La mejora de D3 es **solo de PRECISIÓN** (métrica compuesta de landmarks), no de velocidad. El relleno del anillo debe ser **visible y tomarse su tiempo**; la pantalla de resultado del examen tampoco se apura. Regla del change: que el alumno **vea y entienda** cada paso por encima de la rapidez.
2. **Valores numéricos en el examen** → SÍ, en un **"Ver detalle técnico" colapsado** (distancia/umbral/similitud), fuera del copy principal en lenguaje claro. Confirmado.
3. **Cue de audio en el match del examen** → SÍ, reusar `playSuccess()` en la pantalla de resultado de match. Confirmado.

### Pendientes (no bloquean el apply)
4. **PAD pasivo server-side (DD-18 Fase 2)**: fuera de alcance de c-67; se abriría un change separado cuando la institución eleve el nivel de impacto.
5. **Umbral de "no coincide" y reintentos en el examen**: hoy `MAX_REINTENTOS=2`; la pantalla de resultado cambia **solo la presentación**, el conteo queda intacto (default).

### Gate de gobernanza
6. **CRÍTICO** → la implementación (`/opsx:apply`) requiere la **aprobación explícita del dueño** (task 0.1). Estado: pendiente de confirmación.
