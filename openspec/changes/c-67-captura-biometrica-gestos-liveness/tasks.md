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
- [x] 4.4 Test: la sonrisa confirma con menor latencia (hold propio/factor) sin saltar el gate de neutralidad. Done: test verde (4 casos RED→GREEN→triangulación: confirma/neutral/invariante/anti-doble-paso)
- [x] 4.5 Implementar la latencia propia de la sonrisa (umbral de hold por reto o factor reducido para `sonreír`). Done: SMILE_GESTURE_HOLD_MS exportado y wired en BiometricCapture.tsx via gestureHoldForReto

## 5. Defensa anti-foto / PAD (capability `biometric-presentation-attack-defense`)

- [x] 5.1 Test (`liveness.test.ts`): una foto estática (varianza ~0, profundidad ~0, sin gestos) NO supera la defensa combinada (`passivePassed=false` + retos no completados). Done: test verde (5.1a/5.1b/5.1c/5.1d — 4 casos RED→GREEN→triangulación)
- [x] 5.2 Verificar que el reto-respuesta usa orden barajado (Fisher-Yates) + dirección de giro aleatoria por intento, y que las tres capas (activo + pasivo + cámara virtual) se reportan al backend. Done: test/asserts de consistencia en enrollmentChallengeDetector.test.ts (5.2a/5.2b/5.2c/5.2d/5.2e) + verificación de código en BiometricCapture.tsx + Biometria.tsx
- [x] 5.3 Documentar en código y specs el alcance honesto (ISO 30107-3 Nivel 1–2 en cliente; no inmunidad a inyección/deepfake; autoridad = re-inferencia server-side + verificación continua + revisión humana). Done: comentarios en liveness.ts (módulo, derivePassiveSignals, passivePassed, clientLivenessOk, detectVirtualCamera); spec biometric-presentation-attack-defense ya documenta el límite honesto
- [x] 5.4 Confirmar que `liveness_ok` (pasivo real), `retos_resueltos` reales y la señal de cámara virtual se propagan en `onComplete` → `enviarBiometriaProctoring` (sin hardcodes). Done: buildBiometriaProctoringPayload (función pura en liveness.ts) + 9 tests de propagación verdes + Biometria.tsx usa la función pura (sin inline hardcodes)

## 6. Pantalla de resultado del examen en lenguaje claro (capability `exam-verification-result-screen`, `identity-match-1to1`)

- [x] 6.1 Test (`Biometria`): tras la verificación, el flujo NO avanza automáticamente; requiere confirmación explícita del alumno (gate "continuar"). Done: test verde (reemplaza el `setTimeout(navigate)` automático)
- [x] 6.2 Implementar la pantalla de resultado "coincide": copy claro + botón explícito "Continuar al examen". Done: gate funcionando
- [x] 6.3 Implementar la pantalla de resultado "no coincide": copy claro + opciones reintentar/escalar a una persona (preservar `MAX_REINTENTOS`). Done: sin avance automático
- [x] 6.4 Test de lenguaje claro: el copy principal NO contiene "embedding", "coseno", "umbral", "descriptor", "1:1", "distancia". Done: test de ausencia de jerga verde
- [x] 6.5 Mover los valores técnicos (distancia/umbral) a un detalle opcional/tooltip de glosario (`Term`/`term-tooltip-component`); nunca mostrar el vector. Done: detalle opcional colapsado
- [x] 6.6 Preservar la garantía L2.5 en el copy ("ninguna decisión la toma una máquina; siempre la revisa una persona"). Done: mensaje presente

## 7. Cierre

- [x] 7.1 Suite de tests del frontend verde (vitest) para los helpers y componentes tocados. Done: 336/336 tests verde en 34 archivos (`npx vitest run` en frontend/), estable en múltiples corridas. Cero rojos introducidos por c-67.
- [ ] 7.2 Revisión manual final de aceptación del flujo completo en dispositivo. **ÚNICA TASK PENDIENTE.** Durante las sesiones 2026-06-13/14 el dueño probó exhaustivamente en teléfono real (cloudflared) TODO el flujo — captura de referencia (3 gestos, progreso reanudable, audio), verificación del examen, consentimiento, sala de espera y examen — y se corrigieron todos los hallazgos (ver grupo 8, tasks 8.1–8.28). Todo lo demás está testeado (suite 336/336 verde + verificación en navegador real con Playwright). Resta solo la pasada final de aceptación del dueño antes de archivar; no se puede automatizar (requiere cámara/gestos reales).
- [x] 7.3 Confirmar que NO se tocó la cadena de custodia, el cómputo/persistencia del embedding ni el contrato server-side (c-59). Done: `git diff --name-only b4c3e5b^ b4c3e5b` — cero archivos bajo `backend/`; todos los cambios acotados a `frontend/` (UX/visión/auth-frontend) y `openspec/` (artefactos del change). Cadena de custodia server-side intacta.
- [x] 7.4 Confirmar reglas duras. Done: checklist verificado por diff + lectura de código — ver sesión 2026-06-13 grupo 7 en engram.

## 8. Correcciones de UX/flujo y robustez (sesiones 2026-06-13 y 2026-06-14, fuera del scope original pero del mismo dominio)

> Bugs y pulido surgidos al testear el flujo real en teléfono. Aprobados/pedidos por el dueño en la sesión.

- [x] 8.1 Marco BLANCO alrededor de la cámara del óvalo (contenedor) — `CaptureOval.tsx`. Done: contenedor blanco con el video recortado a la elipse.
- [x] 8.2 Quitar el borde azul "todo OK" del óvalo (se mezclaba con el anillo verde de progreso) — solo ámbar=aviso y verde=éxito. Done.
- [x] 8.3 Anti-spoofing: el último reto (y cualquiera tras un cooldown) se confirmaba sin gesto por `dt` inflado del hueco del cooldown. Fix: clamp `dt` a `MAX_FRAME_DT_MS=100` + reset de `lastFrameTimeRef` al avanzar de reto — `BiometricCapture.tsx`. Done: hold real exigido.
- [x] 8.4 No re-mostrar el óvalo titilando durante la fase `procesando` (solo spinner) — `EnrollmentBiometricStep.tsx`. Done.
- [x] 8.5 HTTP 401 al guardar el embedding (token JWT de 15 min expirado): refresh awaitable + retry una vez con el refresh_token en `realFetch` — `jwt.ts`, `provider.ts`, `api.ts`. Done: auto-curación transparente. **Dominio CRÍTICO (auth), aprobado por el dueño.**
- [x] 8.6 Tarjeta amarilla "Completá tu perfil" persistía con perfil completo: el gate comparaba la versión del consentimiento contra el default mock ('2026.1') en vez de la del backend ('v1'). Fix: `ensureConsentVersionSynced()` antes de `puedeRendir`/`getEnrollment` — `api.ts`. Done.
- [x] 8.7 Cambiar la foto desde un perfil completo re-disparaba el wizard (pedía biometría de nuevo). Fix: el paso de foto vuelve al perfil (no a biometría) y oculta el stepper cuando ya hay referencia — `StudentProfile.tsx`. Done.
- [x] 8.8 Pulido de UI del perfil: botón "Mis exámenes" y "Rehacer captura" a estilo `outline` (blanco); "Escanear DNI" mismo tamaño; quitar badge "Opcional" y título en una línea en `Verificación documental`; quitar CTA "Ir a mis exámenes"; copy del banner verde sin guion. Done.
- [x] 8.9 Captura de referencia se colgaba/recargaba (volvía al perfil) en el teléfono: al apretar "Iniciar" se bajaban ~28 MB de modelos de una (WASM 11 MB + 3 `.task` + face-api), crasheando la pestaña por memoria. **Causa raíz**: el `PoseLandmarker` (5.7 MB) se cargaba pero el enrollment NUNCA llama `detectPose`. Fix: `init({ loadPose })` en `RealMediaPipeVisionEngine.ts` (default true para no regresionar harness/proctoring); `enrollmentEngineLoader.ts` pasa `loadPose:false` → −5.7 MB y menos memoria. `detectPose` lanza error claro si se llamó sin Pose. Done (TDD: 3 tests). `VisionEngine.init` ampliado.
- [x] 8.10 Los modelos se re-descargaban en cada captura: ahora se persisten en Cache Storage vía Service Worker acotado SOLO a `/mediapipe/*` y `/models/*` (cache-first; resto pasa de largo). `public/sw.js` + `src/lib/modelPersistence.ts` (`isModelAssetPath`, `registerModelCacheWorker`) registrado en `main.tsx`. Done (TDD: 5 tests del predicado + verificado en navegador real con Playwright: SW controla la página, modelo cacheado, 2ª lectura 46ms→9ms).
- [~] 8.11 (REVERTIDO por pedido del dueño) Se probó precargar los modelos en la pantalla de instrucciones con un botón "Preparando la verificación…". El dueño lo rechazó: prefiere que cargue al apretar "Iniciar captura de referencia" (como antes), y además la precarga se colgaba. Revertido: `EnrollmentBiometricStep.tsx` vuelve al botón directo `onClick={() => setFase('capturando')}`. La carga ocurre dentro del overlay de captura.
- [x] 8.12 Red de seguridad contra "carga infinita": la carga del motor en `BiometricCapture.tsx` se envuelve en `withTimeout` (30s). Si la descarga de modelos stallea en el teléfono, cae al modo manual existente (que captura un frame real) en vez de spinner eterno. `src/lib/withTimeout.ts` + test (TDD: 4 tests). Aplica al enrollment y a la verificación del examen (ambos ya tenían `fallbackManual`).
- [x] 8.13 Anillo de progreso: iba pegado al borde INTERNO del video. Ahora va SOBRE LA BANDA BLANCA que rodea al óvalo (banda `p-[4%]`, anillo centrado `PROGRESS_RX/RY` < borde externo, trazo 3, viewBox `0 0 100 130` + overflow visible) — `CaptureOval.tsx` + test reescrito. La banda blanca se llena de color.
- [x] 8.14 Progreso que "desaparecía" entre pasos: al confirmar un paso el relleno volvía a empezar durante el cooldown (`challengeIndexRef` aún no había incrementado). Fix: `completadosRef` que sube AL confirmar → base MONÓTONA del anillo; el avance logrado nunca retrocede — `BiometricCapture.tsx`.
- [x] 8.15 Animación de éxito: el óvalo ahora se RELLENA de verde sólido (tapa la cámara) con `motion` (motion/react) — check + "Verificado" tipo confirmación de pedido, en vez del velo translúcido con la cámara visible — `CaptureOval.tsx`.
- [x] 8.16 Fase "procesando" del enrollment: ya no muestra "Procesando tu referencia facial…" (reiniciaba la sensación). Ahora continúa el éxito: check verde + "¡Verificación lista!" + "Guardando tu referencia de forma segura…" — `EnrollmentBiometricStep.tsx`.
- [x] 8.17 Copy del examen: se eliminó el jargon "acuse" (lenguaje claro = "confirmación/confirmar") en `AcuseExamen.tsx`, `AlumnoMaterias.tsx`, `AlumnoMisExamenes.tsx`, `InscripcionCard.tsx`. Cero "acuse" visible para el alumno. [[convenci-n-lenguaje-claro-ui-alumno]]
- [x] 8.18 Copy: (a) "Video continuo" → "Se analiza la imagen en vivo… No se graba video: solo una captura puntual ante un evento" (refleja la realidad: screenshot por evento, no grabación) en `ALCANCE_MONITOREO` (`api.ts`); (b) doble "perfil" sin sentido en el consentimiento del examen (`Consent.tsx`) reescrito sin la redundancia.
- [x] 8.19 Requisitos del examen (`EquipmentCheck.tsx`): quitado el badge rojo "CÁMARA EN VIVO"; copy de la preview reescrito ("solo para que verifiques tu cámara, no se envía a nadie hasta empezar"); video en modo selfie (`scaleX(-1)`) consistente con la captura. **(Espejo: pendiente de confirmación del dueño.)**
- [x] 8.20 Anillo del óvalo: el track quedaba GRIS sobre la banda blanca (no pedido). Bajado a casi imperceptible (`rgba(15,23,42,0.05)`) → la banda queda BLANCA y solo el verde de progreso se nota — `CaptureOval.tsx`.
- [x] 8.21 El verde no se llenaba progresivamente (parecía dibujarse solo al completar). Fix: el relleno del segmento activo usa el acumulador (`accumMs/hold`, monótono) en vez de gatearse por `isHoldingNow` (que titilaba con el detector) — `BiometricCapture.tsx`.
- [x] 8.22 Óvalo "viejo" (punteado) que aparecía tras la captura en el examen: reemplazado por un visual limpio y consistente (círculo surface; en 'verificado' se rellena de verde sólido con el check, como la captura) — `Biometria.tsx`.
- [x] 8.23 Consentimiento del examen (`Consent.tsx`): "Ver texto completo" ahora abre un MODAL de solo lectura (no re-presenta el flujo de aceptación del perfil, que no tenía sentido). Copy de confirmación reescrito (más claro/profesional). Quitado el toggle `verTextoCompleto` y el botón "Volver a la confirmación rápida".
- [x] 8.24 "Detalle técnico" de la verificación (`Biometria.tsx`): redactado profesional y legible — porcentajes ("Coincidencia 95% / Mínimo 45%") + explicación 1:1 + garantía de decisión humana, en vez de "Similitud: 0.954 / Referencia: ≥ 0.45".
- [x] 8.25 Examen: no se vuelve a mostrar ningún óvalo después de la captura. El óvalo guía solo queda en 'preparar'; en verificando/verificado/reintento/etc. el resultado lo comunica la columna de la derecha (icono + texto + acción) — `Biometria.tsx`.
- [x] 8.26 Modal "ver texto completo" del consentimiento estaba roto (sin botones / no cerraba): un ancestro con transform (animate-in) atrapaba el `position:fixed`. Fix: renderizar el modal con `createPortal` a `document.body` (z-[100]) — `Consent.tsx`.
- [x] 8.27 Stepper del examen rediseñado igual que el wizard de completar perfil: reutiliza `WizardStepper` (exportado de `EnrollmentStepLayout`). Labels breves DEBAJO del número (visibles en mobile), check verde al completar, anillo en el actual, más aire en mobile. Empieza en el paso 1 (se quitó 'Ingreso'; ahora 1-based: Requisitos/Consentimiento/Verificación/Sala/Examen/Cierre) — `shells.tsx`.
- [x] 8.28 No sonaba el feedback de progreso de la captura en mobile (AudioContext nace 'suspended' y el loop RAF corre fuera de un gesto). Fix: `unlockAudio()` exportado de `sounds.ts`, llamado en el onClick de "Iniciar" (perfil y examen) para resumir el contexto dentro del gesto — `sounds.ts`, `EnrollmentBiometricStep.tsx`, `Biometria.tsx`.
