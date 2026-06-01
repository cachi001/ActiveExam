## Why

El enrollment biométrico del perfil del alumno (`EnrollmentBiometricStep.tsx`) tiene cámara real pero liveness de botones (mock), embedding `Math.random`, y sin fullscreen en móvil: la captura parece funcional pero no detecta nada real. Esto impide testear el flujo E2E de biometría antes de conectar el backend, y ofrece una experiencia móvil incompatible con la captura activa de liveness (pantalla pequeña, layout partido).

## What Changes

- **Detección REAL de retos de liveness** en el enrollment: los retos (`girar_izquierda`, `girar_derecha`, `parpadear`, `acercarse`, `sonreír`) se resuelven por detección continua frame-a-frame con el motor MediaPipe real (`RealMediaPipeVisionEngine`), no por toque de botón. Cada reto tiene una métrica de landmarks definida.
- **Embedding REAL**: reemplaza `Math.random` por `embeddingFromLandmarks(landmarks)` del motor, derivado deterministamente de la geometría facial de los 468 landmarks de Face Mesh.
- **Fullscreen en móvil**: al iniciar captura en dispositivo touch / pantalla chica, el contenedor entra en pantalla completa (`element.requestFullscreen()`). Fallback "fullscreen-like" (`position: fixed; inset: 0`) cuando la API no está disponible (iOS Safari). Salida al completar o cancelar.
- **Loader lazy compartido**: generaliza `harnessEngineLoader.ts` en un `enrollmentEngineLoader.ts` reutilizable (o un loader genérico central) para no duplicar el singleton WASM; el motor sigue siendo import dinámico, fuera del bundle inicial.
- **Fallback/skip para test**: botón de resolución manual de reto visible solo en modo `demo` (cuando el motor no carga o WebGL ausente), para no bloquear el flujo de test en entornos sin WebGL.

## Capabilities

### New Capabilities
- `enrollment-liveness-detection`: loop de detección frame-a-frame en el enrollment, mapeo reto→métrica de landmarks, resolución automática de retos por threshold. Incluye el loader lazy y el ciclo de vida del motor en el componente.
- `enrollment-fullscreen-mobile`: lógica de fullscreen al iniciar captura (requestFullscreen + fallback fixed) y de salida al terminar. Detección de dispositivo móvil/touch.

### Modified Capabilities
- `exam-enrollment`: ningún cambio de requisitos (el enrollment de examen queda fuera de scope; este change es solo el paso biométrico del perfil).
- `student-profile-shell`: (delta menor) el step biométrico del perfil pasa de demo-mock a funcional.
- `harness-model-loader`: se generaliza el loader de C-30/C-32 para ser reutilizable también desde el enrollment (o se crea un loader paralelo con el mismo patrón de singleton).

## Impact

- **Frontend — archivo principal**: `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` (refactor del flujo de captura y liveness).
- **Frontend — nuevo loader**: `frontend/src/vision/enrollmentEngineLoader.ts` (o generalización de `harnessEngineLoader.ts` → `visionEngineLoader.ts`).
- **Reutiliza sin cambio**: `frontend/src/vision/liveness.ts` (lógica pura de pasivo/activo), `frontend/src/vision/MediaPipeVisionEngine.ts` (`embeddingFromLandmarks`, `gazeFromIris`), `frontend/src/vision/RealMediaPipeVisionEngine.ts` (motor real), `frontend/src/vision/harnessEngineLoader.ts` (patrón de singleton a replicar/generalizar).
- **Bundle**: el motor WASM (`@mediapipe/tasks-vision`) sigue en chunk lazy; el bundle inicial no crece.
- **Sin cambio en la API ni el backend**: el embedding y la imagen de referencia siguen pasando por el mismo `api.guardarReferenciaBiometrica`; el backend re-infiere y firma (RN-GLB-01). Esta verificación cliente es para UX/test; la verificación real es server-side (C-12).
- **Datos sensibles**: el embedding real (derivado de landmarks) se trata igual que el simulado — se envía al mock API y no se persiste en claro fuera del flujo existente. No cambia la política de privacidad ni el dato que llega al backend (Ley 25.326 / RN-BIO-07/08).
- **L2.5 intacto**: el sistema sigue sin sancionar automáticamente. El liveness detectado en cliente es UX; el veredicto final sigue siendo humano.
- **Soberanía**: los modelos siguen siendo locales (`frontend/public/mediapipe/`); sin CDN externo en runtime.
