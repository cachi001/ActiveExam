## Why

El flujo pre-examen, el login y las vistas del alumno acumularon fricción de UX que entorpece la rendición y, en un caso, la bloquea por completo. El más grave: el botón de consentimiento del examen **no deja avanzar** porque `examenActivo` llega `null` al entrar al flujo (nunca se setea en la ruta del alumno). A eso se suman elementos visuales redundantes en liveness, una pantalla de spinner intermedia en el consentimiento, un consentimiento de examen que re-muestra todo el texto aunque el alumno ya consintió el tratamiento en su perfil, un login sin "ver contraseña" y con inputs hardcodeados fuera del patrón del sistema, y tarjetas de "Mis exámenes" que se desbordan en mobile.

Este change agrupa **6 fixes de UX** (Grupo A) del camino crítico del alumno. NO incluye gestión de usuarios (eso es C-59).

## What Changes

- **Liveness — limpieza visual**: eliminar la flecha direccional (`←`/`→`) y el texto "hacia la izquierda/derecha" del paso de giro en `CaptureProgress`, y eliminar el label contextual (`contextLabel`) a la izquierda del botón "Cancelar" en `CaptureOverlay`. La detección de giro sigue funcionando igual; solo se quita el chrome redundante.
- **Consentimiento — sin spinner intermedio**: el paso de consentimiento (perfil y examen) deja de mostrar una pantalla de spinner que bloquea el render. El layout aparece de una; los bloques de texto se rellenan cuando llega la respuesta (skeleton ligero / render progresivo), sin pantalla de "Cargando texto de consentimiento…".
- **Consentimiento del examen liviano (1 click)**: en el paso 2 del wizard del examen, si el alumno **ya consintió el tratamiento en el perfil con la versión vigente**, el paso se transforma en una **confirmación corta de un click** ("Ya consentiste el tratamiento el [fecha]. Confirmá que aceptás ser supervisado en esta evaluación"). Se **sigue registrando** el acuse por-rendición (`recordConsent(examen.id)`, cadena de custodia RN-CC). Si NO consintió en el perfil o la versión cambió, se muestra el consentimiento completo como hoy. **AMBOS consentimientos se conservan** (perfil + por-examen).
- **Fix bug bloqueante — `examenActivo` null**: setear `examenActivo` al iniciar el flujo del examen desde "Rendir" (`AlumnoMisExamenes.handleRendir`), de modo que `Consent.aceptar()` no quede inerte. Es la causa raíz: la ruta del alumno `Rendir → /requisitos → /consentimiento` nunca llamaba a `setExamenActivo`.
- **Login — ver/ocultar contraseña + inputs unificados**: agregar botón de ojo (toggle mostrar/ocultar) al campo password de `FormularioJwt`, y migrar los inputs hardcodeados inline del login al patrón del sistema (`FormField` + clase global `.input`), preservando labels, `autoComplete` y accesibilidad.
- **Mis Exámenes — responsive**: agregar breakpoints (`flex-col sm:flex-row`, `min-w-0`, `truncate`/`line-clamp`) a `InscripcionCard` y `ExamenCard` para que nombres largos, badges y botones no se desborden en pantallas chicas (<360px), usando los tokens de espaciado/color del sistema.

Sin cambios de backend: el estado "ya consintió el tratamiento + versión vigente" se deriva de `api.getEnrollment()` (campo `consentimiento.version`) contra `CONSENT_TEXT.version`, ambos ya disponibles client-side.

## Capabilities

### New Capabilities
- `liveness-capture-chrome`: presentación limpia del overlay de captura biométrica — sin flecha direccional ni label contextual redundante en el paso de giro.
- `exam-consent-lightweight`: consentimiento del examen de un click cuando el tratamiento ya fue consentido en el perfil con versión vigente, preservando el acuse por-rendición; consentimiento sin pantalla de spinner intermedia.
- `login-form-ux`: campo de contraseña con toggle mostrar/ocultar e inputs del login unificados al patrón del sistema (FormField + `.input`).
- `student-exam-cards-responsive`: tarjetas de inscripción y de examen sin desbordes en mobile mediante breakpoints y truncado de texto.

### Modified Capabilities
<!-- Ningún requirement spec-level existente cambia su contrato: los fixes son de presentación
     y de wiring de estado. El bug de examenActivo se cubre como nuevo requirement dentro de
     exam-consent-lightweight (el contrato del consentimiento por-examen no cambia: se sigue
     registrando recordConsent). -->

## Impact

- **Frontend (puro)**:
  - `frontend/src/ui/biometric/CaptureProgress.tsx` — quitar bloque de flecha/dirección.
  - `frontend/src/ui/biometric/CaptureOverlay.tsx` — quitar `contextLabel` de la barra superior (y, si queda huérfano, la prop).
  - `frontend/src/screens/Consent.tsx` — render sin spinner; rama liviana de 1 click; lectura de enrollment.
  - `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx` — quitar pantalla `cargandoTexto`.
  - `frontend/src/screens/AlumnoMisExamenes.tsx` — setear `examenActivo` en `handleRendir`.
  - `frontend/src/screens/Login.tsx` — toggle de password + inputs con FormField/`.input` en `FormularioJwt`.
  - `frontend/src/screens/alumno/components/InscripcionCard.tsx` y `ExamenCard.tsx` — responsive.
- **Store**: uso de `setExamenActivo` (ya existe); lectura de `examenActivo` en Consent (sin cambios de shape).
- **API**: sin cambios. Se reutiliza `api.getEnrollment()`, `api.getExam()`/catálogo, `api.recordConsent()`, `CONSENT_TEXT.version`.
- **Sin backend, sin migraciones, sin nuevos tipos.** Componentes UI compartidos (`Icon`, `FormField`, `Button`, `Card`, `Badge`) se reutilizan, no se duplican.
- **Reglas duras respetadas**: el acuse por-rendición (RN-CC) se conserva; el consentimiento sigue siendo acción afirmativa (RN-CO-02, Ley 25.326); PascalCase en componentes; sin build ni commit automático.
