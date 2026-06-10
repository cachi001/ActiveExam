## Context

La captura de referencia biométrica está implementada en el cliente (`frontend/src/ui/BiometricCapture.tsx` + `frontend/src/ui/biometric/*` + `frontend/src/vision/enrollmentChallengeDetector.ts`). El loop RAF ya hace: liveness pasivo (ventana N=15), detección de cámara virtual, baseline neutral, evaluación secuencial de retos (C-54) y guía de encuadre con histéresis (`framingGuide.ts`). El feedback de audio existe (`sounds.ts`: success/step/hint).

Este change corrige defectos sobre ese código, sin tocar la cadena de custodia ni el cómputo del embedding. La criticidad de dominio es **MEDIA-ALTA**: se modifica el comportamiento del liveness (señal de seguridad) y el flujo de renovación de un dato sensible (Ley 25.326), pero no la criptografía de custodia ni el almacenamiento del embedding.

## Goals / Non-Goals

**Goals:**
- Que las advertencias de encuadre bloqueantes **detengan** la evaluación de retos (no se puede "adivinar"/saltar el gesto con poca luz o dos rostros).
- Confirmar gestos por **tiempo sostenido** (independiente del framerate) y garantizar un avance por gesto.
- Alinear el anillo de progreso del óvalo (quitar la rotación inválida sobre la elipse).
- Mejorar la exposición real del sensor sin contaminar el frame persistido.
- Agregar sonido de fallo.
- Permitir re-captura con límite suave + auditoría, conservando la referencia previa.

**Non-Goals:**
- NO se modifica el liveness pasivo ni la detección de cámara virtual (se preservan).
- NO se cambia el cómputo del embedding, el cifrado at-rest ni la cadena de custodia criptográfica.
- NO se agrega post-proceso de imagen sobre el frame de referencia.
- NO se reescribe el catálogo de advertencias (ya existen las 7); solo se clasifican bloqueantes vs informativas.
- NO se construye un nuevo flujo de renovación (el botón ya existe); solo se le agrega límite + audit.

## Decisions

### D1 — Gate de encuadre con corte temprano en el loop, reusando el patrón de cooldown
Se agrega un chequeo `if (framingHintRef.current es bloqueante) { ...continuar loop sin evaluar reto... return }` justo antes de la sección de evaluación secuencial (después del bloque baseline y del gate de cooldown). Se reusa el mismo `requestAnimationFrame(...); return;` que ya usa `cooldownActiveRef`.
- **Alternativa descartada**: mover la decisión al detector puro (`evaluateChallengeRelative`). Rechazada porque el detector es PURO (sin estado de hint) y debe seguir siéndolo; el gate es responsabilidad del orquestador (el componente).
- La clasificación bloqueante/informativo vive en `framingGuide.ts` como un set/predicado exportado (`isHintBloqueante(hint)`), para testearlo puro.

### D2 — Confirmación por tiempo con marca monótona, no por frames
Se reemplaza la condición de aceptación `count >= framesMinForChallengeSeq` por un sostenimiento temporal: se guarda el `performance.now()` del primer frame que cumple (`holdStartRef`), y se confirma cuando `now - holdStart >= HOLD_MS` (constante exportada, default ~500 ms). Si un frame no cumple, `holdStart` se resetea a null.
- **Alternativa descartada**: subir los `FRAMES_MIN_*`. Rechazada porque sigue atado al framerate (60fps → la mitad de tiempo que 30fps); no resuelve la causa.
- El gate de neutralidad (`NEUTRAL_GATE_FRAMES`) se mantiene como condición previa a empezar a contar el hold (evita doble-paso por residuo). El cooldown entre pasos se mantiene.
- El progreso visual del anillo pasa a derivarse de `min(1, (now - holdStart) / HOLD_MS)` para el reto activo (fracción temporal), no de la fracción por frames.

### D3 — Anillo: quitar la rotación de la elipse
En `CaptureOval.tsx` se elimina `transform="rotate(-90 50 65)"` del `<ellipse>` de progreso. El progreso arrancará en el punto "3 en punto" del óvalo en vez de arriba — un detalle estético aceptable. Si se quisiera arrancar arriba sin rotar, se haría con un `<path>` que empiece en el ápice, pero queda fuera de alcance (over-engineering para un anillo de feedback).
- **Alternativa descartada**: rotar también el track de fondo para que "coincidan entre sí". Rechazada: ambos quedarían apaisados y desalineados respecto del clip-path vertical del video.

### D4 — Exposición vía applyConstraints, best-effort; preview separado del frame guardado
Tras obtener el stream, sobre el video track se intenta `track.applyConstraints({ advanced: [{ exposureMode: 'continuous' }, { brightness: ... }] })` dentro de try/catch (los nombres soportados varían por navegador; se consultan `track.getCapabilities()` antes para no pedir lo no soportado). Cualquier mejora visual adicional para el alumno se hace con filtro CSS sobre el `<video>`, que NO afecta `drawImage(video → canvas)`.
- **Regla dura #6**: `bestReferenceFrameRef` se sigue dibujando del video crudo. Esta separación es la garantía de custodia.

### D5 — playError en el mismo motor WebAudio
Se agrega `playError()` a `sounds.ts` siguiendo el patrón de `playSequence` (tono descendente, ≤250ms, respeta reduced-motion / setSoundEnabled / cooldown). Se dispara desde `BiometricCapture.tsx` en: rama de error de cámara (`setFase('error')`), timeout de baseline sin éxito, y al cierre si `passiveOk === false` o `virtualCameraDetected === true`.

### D6 — Límite suave de re-captura: cliente decide UX, backend audita
- **Cliente**: contador/cooldown de re-capturas en una ventana (puede vivir en el estado del perfil o derivarse del backend). Al alcanzar el límite, el botón "Rehacer/Renovar" se deshabilita con copy explicativo (sin sanción).
- **Backend**: el endpoint de renovación (existente, cadena de custodia) registra en el audit log (usuario, timestamp, origen) y versiona la referencia anterior en lugar de sobre-escribirla. Se reusa el audit log y el almacenamiento existentes (no se agrega tabla nueva si el modelo ya soporta versionado; si no, se evalúa en apply).
- **Gobernanza**: el toque de backend (audit + versionado de referencia) roza datos sensibles → se implementa con checkpoints y se verifica que NO altera la lógica de custodia/embedding.

## Risks / Trade-offs

- **[El umbral de tiempo (~500ms) puede sentirse lento o rápido según el alumno]** → Constante exportada y ajustable sin re-deploy; se calibra con pruebas reales en `/opsx:apply`.
- **[`applyConstraints` de exposición no está soportado uniformemente y puede degradar en algunos devices]** → Best-effort en try/catch con `getCapabilities()` previo; si no se soporta, no se toca nada y queda la guía de luz. Nunca bloquea la captura.
- **[Clasificar `lejos`/`cerca` como bloqueantes podría frustrar en cámaras gran angular]** → Los umbrales de `framingGuide.ts` (BBOX_FAR/NEAR) ya existen; si en pruebas resultan agresivos, se ajustan ahí. El gate sólo agrega el bloqueo, no cambia los umbrales.
- **[El límite suave de re-captura podría bloquear a un alumno legítimo con problemas de cámara]** → Es SUAVE (cooldown temporal, no permanente) y nunca sanciona; siempre puede reintentar tras el cooldown y escalar a vía alternativa/proctor.
- **[Quitar la rotación del anillo cambia dónde arranca el progreso]** → Estético, sin impacto funcional; documentado en D3.

## Migration Plan

- Cambios client-side: sin migración de datos; se despliegan con el frontend.
- Backend (#6): si hace falta versionar la referencia anterior y el modelo aún sobre-escribe, la migración Alembic sería aditiva (columna de versión / tabla de historial) y destructiva-en-dos-pasos según convención del repo. Se decide en `/opsx:apply` tras inspeccionar el modelo actual de referencia.
- Rollback: revertir el frontend restaura el comportamiento anterior; el audit log adicional es aditivo (no rompe nada al revertir).

## Open Questions

- ¿El modelo de datos de la referencia ya soporta versionado/historial, o hay que agregarlo? (Se resuelve inspeccionando el backend en apply.)
- Valor final de `HOLD_MS` y del límite de re-capturas (cooldown + máximo) — calibración con pruebas reales.
- ¿`mucha_luz` (contraluz) debe ser bloqueante o solo advertir? Propuesto bloqueante; confirmar en pruebas de usabilidad.
