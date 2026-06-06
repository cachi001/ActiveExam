## Why

El flujo de verificación biométrica con retos activos tiene un bug crítico de experiencia y seguridad: el primer reto siempre se auto-completa sin que el alumno haga nada, porque los retos se evalúan en paralelo con umbrales absolutos demasiado permisivos que la cara en reposo natural ya satisface (especialmente "sonreír" con umbral 0.10 y "acercarse" con 0.48). Esto rompe el propósito del liveness activo (DD-18) y degrada la confianza en la evidencia biométrica.

El dueño del producto requiere un flujo deliberado y perceptible — al estilo de las apps de banca móvil: retos secuenciales, uno a la vez, confirmación visual clara de cada paso, evaluados contra el baseline neutral del propio usuario (no contra umbrales absolutos globales) para eliminar los falsos positivos en reposo.

## What Changes

- **Retos evaluados en secuencia estricta**, uno a la vez, en **orden aleatorio por intento** (`parpadear`, `girar cabeza` [con dirección aleatoria], `sonreír` barajados con `Math.random()` al iniciar la captura) (máquina de estados, no paralelo). Al completar un reto, el siguiente se habilita explícitamente.
- **Eliminar "acercarse"** del catálogo de retos activos de enrollment. Es frágil, no es estándar de liveness, y requiere estimación de profundidad sin garantías en hardware variado.
- **Baseline neutral + evaluación por delta relativo**: capturar las métricas faciales del usuario en los primeros N frames con cara detectada y estable, y evaluar cada reto como un cambio significativo porcentual respecto a ese baseline. Reemplaza los umbrales absolutos actuales (`SMILE_WIDTH_THRESHOLD=0.10`, `BLINK_CLOSE_THRESHOLD=0.018`, etc.) por thresholds relativos al estado neutral del alumno.
- **Sostenimiento mínimo elevado**: subir `FRAMES_MIN_BLINK` de 1 a 3 y los demás (giro, sonrisa) a 4. Un solo frame no confirma ningún reto; valores bajos mantienen el flujo ágil (~5-7 s totales).
- **Cooldown entre pasos**: período corto (350 ms) entre la confirmación de un reto y la habilitación del siguiente, para evitar saltos instantáneos y mantener el flujo ágil.
- **Confirmación visual deliberada**: pantalla/estado "Paso N completado ✓" explícito antes de habilitar el siguiente reto.
- **Frame de referencia de calidad**: el embedding de enrollment se computa sobre el frame capturado durante la fase de baseline neutral (cara frontal, estable), no sobre el último frame arbitrario del loop.

## Capabilities

### New Capabilities
- `liveness-sequential-challenge-engine`: Motor de retos secuenciales de liveness — máquina de estados (idle → baseline → challenge[N] → cooldown → done), evaluación por delta relativo al baseline neutral del usuario, sostenimiento mínimo elevado y cooldown entre pasos.

### Modified Capabilities
- `biometric-liveness-active`: El flujo de retos activos pasa de evaluación paralela con umbrales absolutos a evaluación secuencial con delta relativo. Cambia el catálogo de retos (elimina `acercarse`), el orden de evaluación, los thresholds y el protocolo de confirmación visual.

## Impact

- **Frontend — lógica de detección**:
  - `frontend/src/vision/enrollmentChallengeDetector.ts` — reemplazar `evaluateChallenge()` con variante relativa-al-baseline; eliminar constantes absolutas obsoletas; agregar función de captura de baseline.
  - `frontend/src/vision/liveness.ts` — actualizar `ACTIVE_CHALLENGES` (remover `acercarse`); agregar tipos para el estado de la máquina de retos secuenciales.
- **Frontend — componente de captura**:
  - `frontend/src/ui/BiometricCapture.tsx` — reemplazar el loop `for (const id of currentDesafios)` paralelo por una máquina de estados secuencial; agregar fase `baseline`; implementar cooldown y confirmación visual entre pasos; actualizar el frame de referencia para el embedding.
- **Frontend — UI de feedback**:
  - `frontend/src/ui/CaptureProgress.tsx` (o equivalente) — mostrar "Paso N ✓ completado" y el siguiente reto de forma deliberada.
- **Sin cambios en backend**: el change es 100 % frontend. El backend recibe el mismo callback `onComplete` con los mismos parámetros; la lista de `retosResueltos` cambiará de contenido (sin `acercarse`) pero la firma es compatible.
- **Sin cambios en specs de verificación de examen**: la verificación biométrica durante el examen (`Biometria.tsx`) usa `BiometricCapture` como componente; se beneficia del fix pero no requiere cambios propios si su catálogo de retos ya no incluye `acercarse`.
