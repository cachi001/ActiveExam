## Context

El frontend tiene dos flujos donde se captura biometría:

1. **Examen** (`/biometria`, `Biometria.tsx`): pre-rendición. Hoy es mock puro — los retos de liveness se resuelven con botones (`onClick={() => resolver(d.id)}`). Card chica centrada (~280×340 px), sin fullscreen, sin detección real.
2. **Perfil** (`/alumno/perfil`, `EnrollmentBiometricStep.tsx`): enrollment de referencia. Implementado en C-34: loop RAF real, `evaluateChallenge`, `loadEnrollmentEngine`/`disposeEnrollmentEngine`, fullscreen solo en móvil, fallback manual, embedding real con `embeddingFromLandmarks`.

Las dos pantallas no comparten componente — están duplicadas en lógica y UI. La brecha más crítica es que el examen no tiene detección real, lo que invalida el liveness de pre-rendición.

El motor y el evaluador ya existen y están probados:
- `enrollmentEngineLoader.ts`: lazy singleton, ciclo de vida independiente del harness.
- `enrollmentChallengeDetector.ts`: evaluador puro (girar, parpadear, acercarse, sonreír) con thresholds exportados.
- `liveness.ts`: `ACTIVE_CHALLENGES` (incluye `parpadear`), `pickActiveChallenges`.

Restricciones duras: NO buildear; motor LAZY (sin import estático de @mediapipe/tasks-vision); cliente = sensor no confiable (re-inferencia server-side, C-12); embedding = dato sensible (Ley 25.326); L2.5 intacto.

## Goals / Non-Goals

**Goals:**
- Un componente compartido `BiometricCapture` que encapsula cámara + detección real + UI inmersiva.
- Ambas pantallas (Biometria.tsx y EnrollmentBiometricStep.tsx) usan `BiometricCapture` — eliminar duplicación y el mock del examen.
- UI inmersiva funcional en desktop y móvil: overlay `fixed inset-0` + óvalo dominante + paso actual abajo + progreso de retos.
- Fullscreen real (`requestFullscreen()`) donde esté disponible; fallback CSS `fixed inset-0` en iOS Safari y desktop sin API.
- Parpadeo (`parpadear`) incluido en el set de retos aleatorios y detectado con el motor real.
- Fallback manual cuando el motor no puede cargar (WebGL ausente).

**Non-Goals:**
- Foto de perfil / avatar institucional — diferido a change posterior.
- Cambios en el backend o en `api.verifyIdentity()` / `api.guardarReferenciaBiometrica()`.
- Nuevo loader de motor — se reutiliza `enrollmentEngineLoader` tal cual.
- Cambios en routing o en el flujo post-verificación de ninguna pantalla.

## Decisions

### D-1: Componente compartido `BiometricCapture` en `frontend/src/ui/`

**Decisión**: Un componente `BiometricCapture.tsx` en `frontend/src/ui/` (capa UI compartida, consistente con `Term.tsx`, shells, etc.). Encapsula toda la lógica de captura: getUserMedia, loop RAF, `loadEnrollmentEngine`/`disposeEnrollmentEngine`, `evaluateChallenge`, `pickActiveChallenges`, y la UI inmersiva.

**API de props**:
```ts
interface BiometricCaptureProps {
  /** Retos a usar. Si no se pasa, pickActiveChallenges(2) elige aleatoriamente. */
  challenges?: ActiveChallenge[];
  /** Número de retos a elegir si no se pasan explícitamente (default: 2). */
  challengeCount?: number;
  /** Texto de contexto mostrado en el encabezado del overlay (ej. "Verificación de identidad"). */
  contextLabel?: string;
  /** Callback al completar todos los retos. Recibe los landmarks del último frame. */
  onComplete: (landmarks: FaceLandmark[]) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
}
```

**Alternativa descartada**: generalizar `harnessEngineLoader` o crear un nuevo loader. Rechazado por D-1 de C-34 — ciclos de vida independientes, evitar cascada de cambios en specs de C-30/C-32. Se reutiliza `enrollmentEngineLoader` sin modificar.

### D-2: Overlay `fixed inset-0` como estrategia fullscreen cross-platform

**Decisión**: El overlay inmersivo usa `fixed inset-0 z-50` con fondo sólido (ej. `bg-neutral-950` o `bg-inverse-surface`) como capa base. Esto funciona en desktop (cubre toda la ventana del navegador) y en móvil sin necesidad de fullscreen nativo. Sobre esto, se intenta `requestFullscreen()` en el elemento raíz del overlay cuando esté disponible — en desktop moderno y Android Chrome esto elimina la barra del navegador; en iOS Safari y entornos sin API el fallback CSS es suficiente.

```
Orden de resolución:
1. fixed inset-0 z-50 (siempre activo — base del overlay)
2. requestFullscreen() en el elemento contenedor (si disponible, intento best-effort)
3. Fallback: solo el CSS (ya cubre la pantalla visual, barra del browser visible pero experiencia inmersiva)
```

**Diferencia con C-34**: C-34 solo activaba fullscreen en móvil (`isMobileOrTouch()`). C-36 activa el overlay `fixed inset-0` en TODOS los dispositivos, sin condición. `requestFullscreen()` se intenta siempre (no solo en móvil), y el fallback CSS siempre está activo.

**Alternativa descartada**: `position: absolute` con portal o `dialog[fullscreen]`. Rechazado por complejidad y problemas de z-index en iOS.

### D-3: Layout del overlay — estructura visual

```
┌─────────────────────────────────────────────────────┐
│  [Cancelar ×]                          (top-right)  │ ← botón discreto, text-sm, opacity-60
│                                                     │
│           ╭──────────────────╮                      │
│           │                  │  ← óvalo con video   │
│           │   VIDEO CÁMARA   │     dominante        │
│           │                  │     ~70-80% vh       │
│           ╰──────────────────╯                      │
│                                                     │
│         "Parpadeá"            (texto grande)        │ ← paso actual
│         ●●○  2 / 3            (progreso)            │ ← dots + contador
└─────────────────────────────────────────────────────┘
```

- **Óvalo**: `aspect-[3/4]` con `max-h-[70vh]`, rounded-full, overflow-hidden. El video `object-cover` dentro.
- **Paso actual**: `text-title-xl` o `text-headline-sm`, bold, centrado abajo. Color de acento cuando está activo, success cuando resuelto.
- **Progreso**: dots (●/○) + texto "N / total". Transición de color cuando se completa un reto.
- **Chrome mínimo**: sin encabezados extra, sin cards con bordes, sin padding innecesario.
- **Spinner de motor**: overlay sobre el óvalo (bg-black/60) mientras `loadEnrollmentEngine` resuelve.

### D-4: Parpadeo en el set de retos

**Decisión**: `parpadear` ya está en `ACTIVE_CHALLENGES` y `evaluateChallenge`. `pickActiveChallenges(2)` puede incluirlo. El componente no filtra retos — todos los que devuelva `pickActiveChallenges` son válidos. El threshold `BLINK_CLOSE_THRESHOLD = 0.015` (apertura < 1.5% del alto del frame) ya está calibrado en C-34.

**Labels de retos** (para mostrar en el paso actual):
```
girar_izquierda → "Mirá a la izquierda"
girar_derecha   → "Mirá a la derecha"
parpadear       → "Parpadeá"
acercarse       → "Acercate a la cámara"
sonreir         → "Sonreí"
```
Estos se obtienen de `DESAFIOS` de `lib/api.ts` (campo `label`) — igual que hoy.

### D-5: Refactor de las dos pantallas usando `BiometricCapture`

**Biometria.tsx** (examen):
- Importa `BiometricCapture`.
- En fase `capturando`: renderiza `<BiometricCapture onComplete={handleComplete} onCancel={handleCancel} />`.
- `handleComplete(landmarks)`: calcula embedding con `embeddingFromLandmarks(landmarks)`, llama `verificar()` con el embedding real (en lugar de `api.verifyIdentity(examen.id, 0.31)` con distancia hardcodeada).
- Mantiene el flujo de fases `preparar → capturando → verificando → verificado/reintento` y la navegación post-verificación a `/sala-espera`.

**EnrollmentBiometricStep.tsx** (perfil):
- Importa `BiometricCapture`.
- En fase `capturando`: renderiza `<BiometricCapture onComplete={handleComplete} onCancel={cancelarCaptura} />`.
- `handleComplete(landmarks)`: calcula embedding, llama `api.guardarReferenciaBiometrica()` y pasa a fase `completado`.
- Mantiene el encabezado contextual (renovación, nota de privacidad Ley 25.326) y el callback `onCapturada` — solo delega la captura.
- Elimina: loop RAF, `engineRef`, `challengeCountsRef`, `startDetectionLoop`, `resolverRetoFromLoop`, `resolverRetoManual`, `activarFullscreen`, `salirFullscreen`, y toda la UI de retos inline.

### D-6: Fallback manual

Cuando `loadEnrollmentEngine()` rechaza (WebGL ausente), `BiometricCapture` entra en modo fallback: los retos se muestran como botones clicables (igual que C-34). Se muestra un banner de advertencia "Motor de visión no disponible — modo de prueba manual". El fallback es honesto: no garantiza liveness real, pero permite completar el flujo demo.

## Risks / Trade-offs

- **iOS Safari fullscreen limitado** → Mitigación: el overlay `fixed inset-0` ya da experiencia inmersiva sin `requestFullscreen()`; `requestFullscreen()` es best-effort. La experiencia funcional en iOS está garantizada por el CSS.
- **Performance del loop RAF en desktop de baja gama** → Mitigación: el loop ya es probado en C-34; `BiometricCapture` hereda el mismo patrón (bitmap → Promise.all detectFaceMesh/detectFaces). No se cambia la frecuencia del loop.
- **No romper el flujo del examen** → Mitigación: `Biometria.tsx` mantiene su máquina de estados y navegación; solo la fase `capturando` delega a `BiometricCapture`. Las fases `preparar`, `verificando`, `verificado`, `reintento` no cambian.
- **No romper el gate del perfil** → Mitigación: `EnrollmentBiometricStep` mantiene su `onCapturada` callback y toda la lógica post-captura; solo delega la UI y el loop de detección a `BiometricCapture`.
- **Embedding desde examen (nuevo)** → El examen hoy llama `api.verifyIdentity(examen.id, 0.31)` con distancia hardcodeada. Con `BiometricCapture`, se obtendrá un embedding real del último frame antes de llamar a `verifyIdentity`. En el mock API, `verifyIdentity` no usa el embedding (lo ignora), pero la UI puede pasarlo para preparar C-09 real. Riesgo: ninguno en demo; la API mock no valida.
- **Foto de perfil diferida** → No está en alcance. El proposal lo menciona explícitamente como follow-up. No afecta el gate `puedeRendir()` ni el flujo de verificación.
