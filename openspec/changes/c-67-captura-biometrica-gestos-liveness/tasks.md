# Tasks — C-67 `captura-biometrica-gestos-liveness`

> Mejoras de UX y robustez del flujo biométrico client-side. **Dominio CRÍTICO (biometría + anti-spoofing): NO escribir código sin aprobación humana explícita del dueño (ver design.md §Gobernanza).** Estas tasks son un checklist para el futuro `/opsx:apply`, no se implementan en este propose.
>
> Strict TDD: el frontend tiene runner (vitest; existen `*.test.ts` en `frontend/src/ui/biometric/` y `frontend/src/vision/`). Donde aplique, escribir el test ANTES (RED → GREEN → triangular). La lógica DOM/SVG/audio que vitest no cubre bien se valida con tests de los helpers puros + revisión visual. Ningún test mockea la DB (regla dura #4). No buildear ni commitear sin pedido (reglas duras #1, #2).

## 0. Gate de aprobación (CRÍTICO)

- [x] 0.1 Obtener aprobación humana explícita del dueño del producto para implementar (dominio CRÍTICO: biometría + anti-spoofing). Sin esta aprobación, no se escribe código. — Aprobado 2026-06-13.
- [x] 0.2 Confirmar con el dueño las Open Questions del design (latencia de sonrisa, mostrar/ocultar valores técnicos, cue de audio en match del examen). — Confirmado 2026-06-13.

## 1. Anillo de progreso en el borde exterior + trazo fino (capability `biometric-gesture-progress-ring`, `biometric-capture-av-feedback`)

- [x] 1.1 Test de render de `CaptureOval`: el `<ellipse>` de progreso usa radios del borde exterior y el track/fill comparten orientación vertical (sin rotación). Done: test verde
- [x] 1.2 Reubicar el `<ellipse>` de progreso al borde exterior del óvalo (fuera del recorte del video), preservando el `viewBox`/`preserveAspectRatio`. Done: anillo en el contorno externo
- [x] 1.3 Reducir el grosor del trazo del anillo y del track (minimalista). Done: trazo fino
- [x] 1.4 Hacer que el trazo de progreso vire a verde durante el llenado del gesto activo (no solo en éxito). Done: relleno verde tipo barra de carga
- [x] 1.5 Revisión visual en mobile y desktop (aspect ratios) — anillo alineado con el recorte. Done: revisión iterativa en teléfono (cloudflared) + desktop; óvalo elíptico real, anillo en borde exterior, marco blanco alrededor de la cámara

## 2. Progreso acumulado con reanudación sin reinicio (capability `biometric-gesture-progress-resume`, `biometric-gesture-hold-timing`)

- [x] 2.1 Test (helper puro): acumulador de tiempo efectivo de gesto cumplido por reto — preserva el progreso al perder el gesto y reanuda al recuperarlo; confirma al alcanzar `GESTURE_HOLD_MS`. Done: test RED→GREEN + triangulación (gesto continuo / con pérdida / múltiples pérdidas)
- [x] 2.2 Implementar el acumulador `gestureAccumMs` por reto en `BiometricCapture.tsx`, sumando `dt` mientras el gesto se cumple y preservándolo al perderse. Done: implementado
- [x] 2.3 Calcular `fracReto = min(1, gestureAccumMs / GESTURE_HOLD_MS)` y derivar `progreso = (retosCompletos + fracReto) / total` desde el acumulador (no desde `holdStart`). Done: progreso reanuda sin reinicio
- [x] 2.4 Reiniciar el acumulador al confirmar el reto y al avanzar a otro reto; preservar el gate de neutralidad y el anti doble-paso (C-65). Done: test de "un gesto = un avance" sigue verde
- [x] 2.5 Ocultar el relleno del gesto activo al perder el gesto sin descartar el acumulado. Done: relleno se oculta, progreso persiste

## 3. Señales auditivas de progreso y pérdida (capability `biometric-gesture-audio-cues`, `biometric-capture-av-feedback`)

- [x] 3.1 Test de `sounds.ts`: `playGestureProgress()` y `playGestureLost()` respetan `prefers-reduced-motion`, `setSoundEnabled(false)` y el cooldown por nombre. Done: test verde (patrón de `sounds.test.ts`)
- [x] 3.2 Agregar `playGestureProgress()` (tick breve agudo) y `playGestureLost()` (tono grave corto, distinto de `playError`/`playHint`) al catálogo. Done: implementado
- [x] 3.3 Disparar `playGestureProgress()` por cruce de fracción de progreso (no por frame) desde `BiometricCapture`. Done: no estalla en bucle
- [x] 3.4 Disparar `playGestureLost()` cuando el gesto se pierde con progreso acumulado > 0 y el relleno se oculta. Done: suena una vez al perder

## 4. Sonrisa más precisa y más rápida (capability `biometric-smile-precision`)

- [x] 4.1 Test (`enrollmentChallengeDetector.test.ts`): métrica de sonrisa compuesta (ancho + elevación de comisuras relativa al baseline) confirma sonrisa real, NO confirma cara neutral, NO confirma boca abierta sin sonreír. Done: test RED→GREEN + triangulación
- [x] 4.2 Implementar la métrica compuesta de sonrisa en `evaluateChallengeRelative` (incorporar elevación de comisuras 61/291 relativa a un punto estable), manteniendo evaluación relativa al baseline. Done: implementado
- [x] 4.3 Afinar el umbral relativo de la métrica compuesta sin reabrir el auto-OK en reposo (validar con `isBaselineSmileValid`). Done: tests de reposo verdes
- [ ] 4.4 Test: la sonrisa confirma con menor latencia (hold propio/factor) sin saltar el gate de neutralidad. Done: test verde
- [ ] 4.5 Implementar la latencia propia de la sonrisa (umbral de hold por reto o factor reducido para `sonreír`). Done: confirma más rápido

## 5. Defensa anti-foto / PAD (capability `biometric-presentation-attack-defense`)

- [ ] 5.1 Test (`liveness.test.ts`): una foto estática (varianza ~0, profundidad ~0, sin gestos) NO supera la defensa combinada (`passivePassed=false` + retos no completados). Done: test verde
- [ ] 5.2 Verificar que el reto-respuesta usa orden barajado (Fisher-Yates) + dirección de giro aleatoria por intento, y que las tres capas (activo + pasivo + cámara virtual) se reportan al backend. Done: test/asserts de consistencia
- [ ] 5.3 Documentar en código y specs el alcance honesto (ISO 30107-3 Nivel 1–2 en cliente; no inmunidad a inyección/deepfake; autoridad = re-inferencia server-side + verificación continua + revisión humana). Done: comentarios/specs coherentes
- [ ] 5.4 Confirmar que `liveness_ok` (pasivo real), `retos_resueltos` reales y la señal de cámara virtual se propagan en `onComplete` → `enviarBiometriaProctoring` (sin hardcodes). Done: test de propagación verde

## 6. Pantalla de resultado del examen en lenguaje claro (capability `exam-verification-result-screen`, `identity-match-1to1`)

- [ ] 6.1 Test (`Biometria`): tras la verificación, el flujo NO avanza automáticamente; requiere confirmación explícita del alumno (gate "continuar"). Done: test verde (reemplaza el `setTimeout(navigate)` automático)
- [ ] 6.2 Implementar la pantalla de resultado "coincide": copy claro + botón explícito "Continuar al examen". Done: gate funcionando
- [ ] 6.3 Implementar la pantalla de resultado "no coincide": copy claro + opciones reintentar/escalar a una persona (preservar `MAX_REINTENTOS`). Done: sin avance automático
- [ ] 6.4 Test de lenguaje claro: el copy principal NO contiene "embedding", "coseno", "umbral", "descriptor", "1:1", "distancia". Done: test de ausencia de jerga verde
- [ ] 6.5 Mover los valores técnicos (distancia/umbral) a un detalle opcional/tooltip de glosario (`Term`/`term-tooltip-component`); nunca mostrar el vector. Done: detalle opcional colapsado
- [ ] 6.6 Preservar la garantía L2.5 en el copy ("ninguna decisión la toma una máquina; siempre la revisa una persona"). Done: mensaje presente

## 7. Cierre

- [ ] 7.1 Suite de tests del frontend verde (vitest) para los helpers y componentes tocados. Done: `*.test.ts` afectados en verde
- [ ] 7.2 Revisión manual del flujo completo: captura de referencia (3 gestos, progreso reanudable, audio) + verificación del examen (pantalla de resultado, gate). Done: flujo sin freezing, UX clara
- [ ] 7.3 Confirmar que NO se tocó la cadena de custodia, el cómputo/persistencia del embedding ni el contrato server-side (c-59). Done: diff acotado al frontend de UX/visión
- [ ] 7.4 Confirmar reglas duras: L2.5 (sin sanción automática), cliente = sensor no confiable (autoridad server-side), embedding nunca logueado/mostrado, sin jerga en UI. Done: checklist de reglas duras

## 8. Correcciones de UX/flujo y robustez (sesión 2026-06-13, fuera del scope original pero del mismo dominio)

> Bugs y pulido surgidos al testear el flujo real en teléfono. Aprobados/pedidos por el dueño en la sesión.

- [x] 8.1 Marco BLANCO alrededor de la cámara del óvalo (contenedor) — `CaptureOval.tsx`. Done: contenedor blanco con el video recortado a la elipse.
- [x] 8.2 Quitar el borde azul "todo OK" del óvalo (se mezclaba con el anillo verde de progreso) — solo ámbar=aviso y verde=éxito. Done.
- [x] 8.3 Anti-spoofing: el último reto (y cualquiera tras un cooldown) se confirmaba sin gesto por `dt` inflado del hueco del cooldown. Fix: clamp `dt` a `MAX_FRAME_DT_MS=100` + reset de `lastFrameTimeRef` al avanzar de reto — `BiometricCapture.tsx`. Done: hold real exigido.
- [x] 8.4 No re-mostrar el óvalo titilando durante la fase `procesando` (solo spinner) — `EnrollmentBiometricStep.tsx`. Done.
- [x] 8.5 HTTP 401 al guardar el embedding (token JWT de 15 min expirado): refresh awaitable + retry una vez con el refresh_token en `realFetch` — `jwt.ts`, `provider.ts`, `api.ts`. Done: auto-curación transparente. **Dominio CRÍTICO (auth), aprobado por el dueño.**
- [x] 8.6 Tarjeta amarilla "Completá tu perfil" persistía con perfil completo: el gate comparaba la versión del consentimiento contra el default mock ('2026.1') en vez de la del backend ('v1'). Fix: `ensureConsentVersionSynced()` antes de `puedeRendir`/`getEnrollment` — `api.ts`. Done.
- [x] 8.7 Cambiar la foto desde un perfil completo re-disparaba el wizard (pedía biometría de nuevo). Fix: el paso de foto vuelve al perfil (no a biometría) y oculta el stepper cuando ya hay referencia — `StudentProfile.tsx`. Done.
- [x] 8.8 Pulido de UI del perfil: botón "Mis exámenes" y "Rehacer captura" a estilo `outline` (blanco); "Escanear DNI" mismo tamaño; quitar badge "Opcional" y título en una línea en `Verificación documental`; quitar CTA "Ir a mis exámenes"; copy del banner verde sin guion. Done.
