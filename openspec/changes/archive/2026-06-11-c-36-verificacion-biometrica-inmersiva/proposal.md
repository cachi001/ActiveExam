## Why

La verificación biométrica en el examen (`/biometria`) usa botones manuales para simular retos (mock puro), mientras que el enrollment del perfil ya tiene detección real pero ambas pantallas son componentes separados con UI card pequeña centrada — no inmersiva. El resultado es una experiencia fragmentada, inconsistente entre contextos, y en el caso del examen, sin validez funcional real de liveness. Este change unifica la captura en un componente compartido con UI inmersiva estilo app de banco (fullscreen, óvalo dominante, paso actual prominente), reutilizando el motor ya probado en C-34.

## What Changes

- **Nuevo componente compartido** `BiometricCapture` (`frontend/src/ui/BiometricCapture.tsx`): encapsula cámara, loop RAF de detección real, UI inmersiva (overlay `fixed inset-0`, óvalo dominante, paso actual abajo), fallback manual. Reusable desde cualquier contexto.
- **Refactor `Biometria.tsx`** (`frontend/src/screens/Biometria.tsx`): reemplaza el mock con botones por `BiometricCapture`, elimina el loop manual de `resolver()`, mantiene la lógica de `verificar()` y navegación post-verificación.
- **Refactor `EnrollmentBiometricStep.tsx`** (`frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx`): delega la captura al nuevo `BiometricCapture`, retiene el encabezado contextual de enrollment (renovación, nota de privacidad Ley 25.326) y el callback `onCapturada`.
- **UI inmersiva unificada**: overlay `fixed inset-0` (funciona en desktop y móvil, incluido iOS Safari) + `requestFullscreen()` como refuerzo donde esté soportado. Óvalo grande centrado con la cámara. Paso actual (texto grande, ej. "Parpadeá", "Mirá a la izquierda") abajo con indicador de progreso (ej. "2 / 3"). Botón cancelar discreto.
- **Parpadeo incluido y verificado**: el reto `parpadear` ya está implementado en `enrollmentChallengeDetector.ts` y en `ACTIVE_CHALLENGES` de `liveness.ts`; el componente lo incluye en el set de retos aleatorios y lo detecta con el motor real.
- **Desktop explícitamente soportado**: el overlay `fixed inset-0` cubre toda la ventana del navegador en desktop sin necesidad de fullscreen nativo. `requestFullscreen()` se intenta donde esté disponible y soportado; en desktop sin fullscreen API simplificado el overlay CSS basta.
- **Motor lazy preservado**: `loadEnrollmentEngine` / `disposeEnrollmentEngine` (C-34) se reutilizan tal cual; el dynamic import mantiene @mediapipe/tasks-vision fuera del bundle inicial.

## Capabilities

### New Capabilities
- `biometric-capture-component`: Componente compartido `BiometricCapture` — interfaz de props, loop de detección, UI inmersiva (overlay, óvalo, paso actual, progreso de retos, fallback manual).

### Modified Capabilities
- `exam-enrollment`: La pantalla `/biometria` pasa de mock a detección real usando `BiometricCapture`; se eliminan los botones de simulación y el estado `resueltos` manual.
- `student-profile-shell`: El paso biométrico del perfil delega la captura a `BiometricCapture` en lugar de implementar su propia UI de captura; el encabezado contextual y el callback `onCapturada` se mantienen.

## Impact

- **Archivos modificados**: `frontend/src/screens/Biometria.tsx`, `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx`.
- **Archivos creados**: `frontend/src/ui/BiometricCapture.tsx`.
- **Archivos reutilizados sin cambio**: `frontend/src/vision/enrollmentEngineLoader.ts`, `frontend/src/vision/enrollmentChallengeDetector.ts`, `frontend/src/vision/liveness.ts`.
- **Sin cambios en API mock**: `api.verifyIdentity()` y `api.guardarReferenciaBiometrica()` no cambian; `BiometricCapture` recibe callbacks.
- **Sin cambios en routing**: las rutas `/biometria` y `/alumno/perfil` permanecen; el componente interno cambia.
- **Fuera de alcance**: foto de perfil / avatar institucional — diferido a change posterior.
