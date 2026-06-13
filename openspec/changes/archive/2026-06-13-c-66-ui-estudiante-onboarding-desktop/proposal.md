# Proposal — C-66 `ui-estudiante-onboarding-desktop`

> **Naturaleza del change**: ajustes de **UI/UX** del flujo del estudiante. Frontend-only — no toca backend, no toca migraciones, no toca Vercel deploy config. Bug fix de carga + adaptación a desktop + unificación de spinners.

## Why

El workflow del estudiante está muy adaptado a mobile y arrastra varios problemas concretos que detectamos probando el producto con un estudiante registrado:

1. **Onboarding mal priorizado**: al loguearse un estudiante registrado con perfil incompleto, lo primero que tiene que ver es la pantalla que muestra `captura.png` — saludo + identificación + card amarillo "Completá tu perfil antes de rendir" con CTA para completar. Hoy esa información no aparece centrada como primera vista del onboarding.
2. **Falta de navegación hacia atrás**: las pantallas del workflow del estudiante no tienen botón "volver atrás" consistente, lo que rompe la expectativa básica de navegación.
3. **Layout que no usa el ancho desktop**: el contenido está dimensionado para mobile y deja grandes franjas vacías en pantallas grandes.
4. **Bug visible en `Consent.tsx`**: al entrar el alumno ve el checkbox + botón "Acepto y continúo" RENDERIZADOS antes que las cláusulas del consentimiento (`useEffect` carga `getConsentText` en paralelo y la grilla de bloques renderiza con `texto?.bloques ?? []`, mientras checkbox/botón salen siempre). UX confunde — parece que se puede aceptar sin leer.
5. **Spinners inconsistentes**: la pantalla de "Cargando perfil…" (`StudentProfile.tsx:214`) usa spinner gris; el de scaneo biométrico (`EnrollmentBiometricStep.tsx:214`) usa morado centrado `text-primary text-[32px]`. Hay que unificar al patrón morado centrado en todas las pantallas.

## What Changes

- **Dashboard de bienvenida del estudiante con onboarding visible**: al entrar el estudiante registrado, lo primero que se muestra es la pantalla de `captura.png` — header con logo + identificación + saludo `Hola, [Nombre] 👋` + email/institución + card amarillo de perfil incompleto con CTA "Completar perfil" (cuando aplica). Todo visible al primer render, sin scroll ni cargas adicionales.
- **Botón "volver atrás" consistente** en cada pantalla del workflow del estudiante (Consent, EnrollmentConsentStep, EnrollmentBiometricStep, EnrollmentDniStep, etc.), con el patrón de UI ya usado en `Consent.tsx` "Volver a la confirmación rápida" pero generalizado.
- **Layout responsive desktop**: el `StudentShell` actual centra el contenido con `max-w-2xl/3xl` — se amplía el contenedor para aprovechar el ancho disponible en desktop sin romper mobile. Layouts de 2 columnas donde el contenido lo permita.
- **Fix del bug de carga en `Consent.tsx`**: si `texto === null` (texto del consentimiento todavía no llegó), NO renderizar el checkbox ni el botón "Acepto". Mostrar **spinner morado centrado** y NADA más hasta que `texto` esté disponible. Cuando llega, mostrar TODO de una vez (cláusulas + checkbox + botón).
- **Spinner unificado en todas las pantallas del estudiante**: cuando una pantalla está en estado de carga, mostrar un spinner morado (`text-primary`) centrado verticalmente y horizontalmente. Reemplazar los spinners grises en `StudentProfile.tsx`, `Consent.tsx`, `EnrollmentConsentStep.tsx` por este patrón.

## Capabilities

### New Capabilities

- `student-dashboard-onboarding`: la pantalla inicial del estudiante registrado con perfil incompleto — header + saludo + identificación + card amarillo de perfil incompleto con CTA "Completar perfil". Es la **primera vista** que ve el estudiante al loguearse.
- `student-workflow-back-navigation`: botón "volver atrás" consistente en todas las pantallas del workflow del estudiante (consent, enrollment biométrico, enrollment DNI), siguiendo el mismo patrón visual y comportamiento.
- `student-shell-desktop-layout`: layout responsive del `StudentShell` que usa todo el ancho disponible en desktop, sin romper la experiencia mobile.
- `consent-screen-blocking-load`: el bug fix de `Consent.tsx` — sin renderizar checkbox/botón hasta que el texto del consentimiento haya cargado completo. Spinner morado centrado mientras carga.
- `unified-loading-spinner`: spinner unificado (morado `text-primary`, centrado vertical y horizontal) usado en todas las pantallas del estudiante en estado de carga.

### Modified Capabilities

(Si los specs canónicos correspondientes existen, se modifican; si no, las capabilities nuevas reemplazan lo que estaba.)

- `student-dashboard-landing` (de archivados c-37/c-42): el contenido y orden de la landing del estudiante cambia para incluir el card de onboarding cuando el perfil está incompleto.
- `student-portal-navigation`: agrega el botón "volver atrás" como parte del patrón de navegación.

## Impact

- **Archivos a modificar** (frontend-only):
  - `frontend/src/screens/StudentDashboard.tsx` (o el componente que renderiza la landing del estudiante)
  - `frontend/src/screens/Consent.tsx` — fix de lazy load + spinner
  - `frontend/src/screens/StudentProfile.tsx` — spinner unificado
  - `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx` — spinner unificado
  - `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` — botón volver (ya tiene spinner OK)
  - `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — botón volver
  - `frontend/src/ui/shells.tsx` (probable) — layout desktop del `StudentShell`
  - `frontend/src/ui/components.tsx` — agregar/exportar componente `LoadingSpinner` reutilizable (morado centrado)
- **Sin cambios**: backend, migraciones, `main_slim.py`, endpoints existentes, contratos de API, ningún dato persistido.
- **Riesgos mitigados**: confusión del alumno al ver el botón aceptar antes que las cláusulas (cumplimiento del consentimiento informado — Ley 25.326 art. 6: "informado"); abandono del onboarding por no saber qué hacer; inconsistencia visual.
- **Actores afectados**: estudiantes (mejora UX del onboarding y del flujo de consentimiento), QA (tests de regresión visual del flujo).
- **NO afecta**: roles staff (proctor/admin), backend de cualquier capacidad, ningún flujo de evidencia, scoring ni revisión humana.
