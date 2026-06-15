# Proposal — C-67 `captura-biometrica-gestos-liveness`

> **Naturaleza del change**: feature de producto sobre el flujo biométrico client-side (captura de referencia + liveness de gestos + verificación 1:1 del examen). Governance **CRÍTICO / seguridad** (biometría + anti-spoofing). **No bloqueante del MVP backend** (c-10→c-20); construye sobre el linaje archivado **c-22 / c-36 / c-54 / c-59 / c-65**. **No depende de c-03** (no toca cola/transporte/tiempo real). El sistema permanece **L2.5**: nunca sanciona automáticamente; la verificación del navegador es UX de conveniencia, la verificación **autoritativa** es la re-inferencia server-side.

## Why

La captura de referencia biométrica y la verificación 1:1 del examen ya están implementadas, pero el dueño del producto detectó defectos de **experiencia** y de **percepción de seguridad** que erosionan la confianza en el liveness y dejan al alumno sin entender qué se verificó:

- **El gesto de sonrisa es lento e impreciso**: tarda en dar OK, frustra al alumno y degrada la señal de liveness (la métrica relativa actual y la confirmación por tiempo no están afinadas para la sonrisa).
- **El feedback de progreso del óvalo está mal ubicado y es tosco**: el anillo se pinta **dentro** del óvalo (sobre la imagen de la cámara), el borde es grueso y poco minimalista, y al sostener un gesto el progreso **se reinicia a cero** si el gesto se pierde un instante — castiga al alumno honesto y no comunica "vas bien, seguí".
- **La verificación del examen "pasa demasiado rápido"**: compara el embedding (distancia coseno) y avanza sin que el alumno **vea ni entienda** el resultado. Hoy el resultado se muestra con jerga ("distancia 0.31 < umbral 0.35", "comparación 1:1 del descriptor") que una persona sin conocimiento técnico no comprende.
- **El anti-spoofing debe endurecerse**: el dueño exige que **ni una foto** pase el liveness. Hay que apoyarse en el reto-respuesta de los 3 gestos + señales pasivas + detección de cámara virtual ya existentes (`liveness.ts`, `virtual-camera-detection`) y dejar explícito el estándar (ISO/IEC 30107-3) y el límite honesto del paradigma cliente.

Ninguno de estos defectos toca la cadena de custodia ni el cómputo del embedding, pero juntos debilitan la primera capa de defensa (liveness) y dejan al alumno sin transparencia sobre la decisión que más le importa: **¿me reconoció como yo?**.

## What Changes

Mejoras de UX y de robustez sobre el flujo biométrico client-side, sin tocar la cadena de custodia ni el cómputo del embedding:

- **Anillo de progreso en el borde EXTERIOR del óvalo**, no dentro de la imagen de cámara. Se reubica el `<ellipse>` de progreso al borde externo del recorte del video; el alumno ve un "loading circular" alrededor del óvalo, no sobre su cara.
- **Borde más fino y minimalista**: se reduce el grosor del trazo del anillo y del track de fondo.
- **Relleno verde progresivo + reanudación sin reinicio**: al sostener el gesto correcto, el anillo se llena de verde gradualmente como una barra de carga circular; si el gesto se **pierde**, el relleno se oculta pero el **progreso acumulado se preserva**, y al **reanudar** el gesto el relleno continúa **desde donde quedó** (no vuelve a cero). El progreso pasa a acumularse por tiempo efectivo de gesto cumplido, no por el `holdStart` actual que se borra al perder el gesto.
- **Señales auditivas de progreso de gesto**: un sonido tipo "tick" mientras el gesto progresa correctamente, y un sonido distinto cuando el progreso **se detiene** (gesto perdido) y el relleno se oculta. Se suman al catálogo de `sounds.ts` (que ya tiene paso/éxito/hint/error).
- **Sonrisa más precisa y más rápida**: se afina la métrica de sonrisa basada en landmarks (no solo ancho de boca: incorporar elevación de comisuras relativa al baseline) y se reduce la latencia de confirmación para el gesto de sonrisa (debounce/umbral propios), sin reabrir falsos positivos en reposo.
- **Pantalla de resultado de la verificación del examen, en lenguaje claro**: tras comparar el embedding, el examen **se detiene** y muestra al alumno un resultado entendible — coincide / no coincide, con una explicación en español cotidiano de qué se verificó — **sin jerga visible** (nada de "embedding", "coseno", "umbral", "descriptor", "1:1"). El alumno debe **ver y reconocer** el resultado antes de poder continuar (gate de "continuar"). Los valores técnicos quedan disponibles solo de forma opcional/secundaria detrás de glosario, nunca como copy principal.
- **Endurecimiento anti-foto (PAD)**: se consolida el reto-respuesta de los 3 gestos secuenciales + señales pasivas (parpadeo, micro-movimientos, profundidad 3D) + detección de cámara virtual como defensa combinada contra ataques de presentación (ISO/IEC 30107-3), reportada al backend. La verificación autoritativa sigue siendo la re-inferencia server-side (regla dura #6).

**BREAKING**: ninguno. La firma de `onComplete` de `BiometricCapture` se conserva; los callbacks de `Biometria.tsx` y `EnrollmentBiometricStep.tsx` siguen siendo compatibles. La nueva pantalla de resultado del examen es un estado adicional, no un cambio de contrato.

## Capabilities

> Cada SHALL se prueba con un test donde aplica el runner (vitest, frontend). La detección de cámara virtual, el liveness pasivo y la verificación server-side se modifican solo en su redacción de PAD/UX; su contrato server-side no cambia.

### New Capabilities

- `biometric-gesture-progress-ring`: el anillo de progreso de la captura se renderiza en el **borde exterior** del óvalo (no sobre la imagen), con trazo fino/minimalista, y se llena de verde progresivamente como barra de carga circular al sostener el gesto correcto.
- `biometric-gesture-progress-resume`: el progreso acumulado de un gesto **se preserva** al perderse el gesto (el relleno se oculta pero no se descarta) y **se reanuda desde donde quedó** al recuperar el gesto, sin reiniciarse a cero.
- `biometric-gesture-audio-cues`: señales auditivas de progreso del gesto — un cue mientras el gesto progresa correctamente y un cue distinto cuando el progreso se detiene (gesto perdido), respetando `prefers-reduced-motion`, el flag de silencio y el cooldown por nombre.
- `biometric-smile-precision`: la detección del gesto de sonrisa usa una métrica de landmarks más precisa (elevación de comisuras relativa al baseline, no solo ancho de boca) y confirma con menor latencia, sin reabrir falsos positivos en reposo.
- `exam-verification-result-screen`: tras la verificación 1:1 del examen, el sistema detiene el flujo y muestra al alumno el resultado (coincide / no coincide) explicado en lenguaje claro, sin jerga visible, y exige una confirmación explícita antes de continuar.
- `biometric-presentation-attack-defense`: la defensa anti-spoofing combina reto-respuesta de los 3 gestos secuenciales + señales pasivas + detección de cámara virtual contra ataques de presentación (ISO/IEC 30107-3), reportada al backend, sin sustituir la re-inferencia server-side ni la decisión humana.

### Modified Capabilities

- `biometric-capture-av-feedback`: el anillo de progreso, además de estar alineado (sin rotación), se reubica al **borde exterior** del óvalo con trazo fino; el catálogo de feedback auditivo incorpora los cues de progreso/pérdida de gesto. Se preservan los sonidos de acierto/paso/error existentes.
- `biometric-gesture-hold-timing`: la confirmación de gesto por tiempo sostenido se conserva, pero el **progreso acumulado** deja de derivarse exclusivamente del `holdStart` (que se reinicia al perder el gesto) y pasa a acumular tiempo efectivo de gesto cumplido, de modo que el relleno reanude sin reiniciar.
- `identity-match-1to1`: la comparación 1:1 por distancia coseno se conserva como **señal de conveniencia client-side**; su resultado SHALL presentarse al alumno en lenguaje claro y gatear el avance del examen, dejando explícito que la verificación autoritativa es server-side.

## Impact

- **Frontend (client-side, MediaPipe / face-api):**
  - `frontend/src/ui/biometric/CaptureOval.tsx` — anillo de progreso al borde exterior, trazo fino, relleno verde progresivo.
  - `frontend/src/ui/BiometricCapture.tsx` — acumulación de progreso por tiempo efectivo (reanudación sin reinicio); disparo de los cues de progreso/pérdida.
  - `frontend/src/ui/biometric/sounds.ts` — nuevos cues `playGestureProgress()` y `playGestureLost()`.
  - `frontend/src/vision/enrollmentChallengeDetector.ts` — métrica de sonrisa más precisa (elevación de comisuras relativa al baseline) + parámetros de latencia propios de la sonrisa.
  - `frontend/src/screens/Biometria.tsx` — pantalla de resultado en lenguaje claro + gate de "continuar"; reubicar la jerga (distancia/umbral) a un detalle opcional/glosario.
- **Backend**: sin cambios. La verificación autoritativa server-side (c-59) y la cadena de custodia se preservan; este change no toca persistencia, cifrado at-rest ni firma.
- **Sin impacto en**: cadena de custodia criptográfica, cómputo/persistencia del embedding, cifrado at-rest, endpoints server-side de verificación. La detección de cámara virtual y el liveness pasivo se conservan funcionalmente (se redactan como parte de la defensa PAD).
- **Reglas duras**: #5 (L2.5, nunca sanción automática; el resultado prioriza, no emite veredicto), #6 (cliente = sensor no confiable; la comparación visible al alumno es conveniencia, la autoritativa es server-side; el frame de referencia no se post-procesa), #7 (embedding = dato sensible, Ley 25.326; nunca se loguea ni se muestra el vector). Lenguaje claro en UI del estudiante (sin jerga visible). PascalCase en componentes React, Conventional Commits sin `Co-Authored-By`, tests sin mocks de DB.
- **Gobernanza**: dominio **CRÍTICO** (biometría + anti-spoofing). La implementación de este change requiere **aprobación humana explícita antes de escribir código** (ver design.md §Gobernanza). Esta propuesta **no implementa nada**.
