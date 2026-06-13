# Design — C-66 `ui-estudiante-onboarding-desktop`

## Context

El producto Active Exam está desplegado en Vercel (frontend) y Railway (backend slim). El frontend está en React + Vite + Tailwind, con un sistema de design tokens propio (`bg-primary-fixed`, `text-on-surface`, etc.). El shell del estudiante hoy es `StudentShell` en `frontend/src/ui/shells.tsx`. Las pantallas del workflow del estudiante son: dashboard de bienvenida → completar perfil (consentimiento + biometría + DNI opcional) → examen.

Stakeholders: el estudiante (usuario principal), QA (regresión visual), futuros mantenedores (que no rompan el patrón unificado).

Inspección rápida del código revela 3 problemas concretos:

1. **`Consent.tsx:28-34, 181-193`**: `useEffect` carga `getConsentText` + `getEnrollment` con `Promise.all`. La grilla de bloques renderiza `(texto?.bloques ?? []).map(...)` — si `texto` es `null`, la grilla es vacía pero el checkbox + botón "Acepto y continúo" siempre renderizan. El comentario `D3 (render progresivo)` fue una decisión consciente del design original que prioriza la velocidad del botón. **Resultado real: rompe el flujo de consentimiento informado** porque el alumno ve el botón antes que las cláusulas y se asume que puede aceptar a ciegas.

2. **`StudentProfile.tsx:214`, `EnrollmentConsentStep.tsx:165`, `Consent.tsx:161/212`**: spinners grises (`ae-spin text-[24px]` o `text-[20px]`, sin `text-primary`). En cambio `EnrollmentBiometricStep.tsx:214` usa `ae-spin text-primary text-[32px]` centrado — patrón visualmente correcto.

3. **`StudentShell`** (a confirmar en lectura) — usa `max-w-2xl/3xl` para el contenido, dejando ~50% del ancho del desktop vacío.

El onboarding del estudiante registrado debe priorizar el card amarillo "Completá tu perfil antes de rendir" (captura del usuario) como primer elemento de la jerarquía visual al ser perfil incompleto, NO como segundo plano después de otras cards.

## Goals / Non-Goals

**Goals**:
- El alumno con perfil incompleto, al loguearse, ve la pantalla exacta de la captura (`captura.png`) como primer render: header + saludo + identificación + card amarillo + CTA.
- Botón "volver atrás" consistente en cada pantalla del workflow del estudiante (consent, enrollment).
- Layout desktop que usa todo el ancho disponible — sin romper mobile.
- `Consent.tsx`: si el texto del consentimiento no llegó, NO renderizar checkbox ni botón — mostrar spinner morado centrado y nada más.
- Spinner unificado (morado centrado) en TODAS las pantallas del estudiante.

**Non-Goals**:
- NO cambiar el backend, los endpoints, los contratos de API ni los modelos de datos.
- NO modificar el flujo de los proctores ni del admin — c-66 es solo del estudiante.
- NO agregar nuevas funcionalidades (ej. dashboard con métricas para el estudiante). Solo arreglar lo que está roto/inconsistente.
- NO refactorizar el sistema de design tokens entero — usar los tokens que ya existen.
- NO migrar pantallas a nuevas librerías de UI ni cambiar versiones de Tailwind/React.
- NO cambiar la lógica de qué pasos del perfil son obligatorios — solo cómo se presentan visualmente.

## Decisions

### D1 — Componente `LoadingSpinner` reutilizable

**Decisión**: crear un componente `LoadingSpinner` en `frontend/src/ui/components.tsx` con la siguiente firma:

```tsx
<LoadingSpinner size="md" /> // default centrado, morado, animado
<LoadingSpinner label="Cargando perfil…" /> // con texto opcional
```

Implementación interna: usa `<Icon name="progress_activity" className="ae-spin text-primary text-[XX]" />` con el tamaño configurable y wrapper centrado (`flex items-center justify-center py-xl`).

**Alternativas consideradas**:
- **Fix in-place en cada archivo**: más rápido pero perpetúa la inconsistencia si alguien agrega una nueva pantalla. Sin abstracción común.
- **Componente con animación CSS custom (no `ae-spin`)**: no aporta — `ae-spin` ya es la animación estándar del proyecto.

**Trade-off aceptado**: una abstracción más en `components.tsx`. Vale la pena porque previene la deriva visual a futuro.

### D2 — Bug fix `Consent.tsx`: bloqueo de render hasta tener `texto`

**Decisión**: agregar un guard al principio del render:

```tsx
// Antes de cualquier UI:
if (texto === null) {
  return (
    <StudentShell step={2}>
      <LoadingSpinner label="Cargando consentimiento…" />
    </StudentShell>
  );
}
// Resto del componente solo se ejecuta con texto != null
```

Eso elimina el bug del botón antes que las cláusulas. El `useEffect` actual queda igual (`Promise.all` está bien para cargar enrollment + texto en paralelo).

**Alternativas consideradas**:
- **Renderizar las cláusulas con un placeholder visual (skeleton)**: agrega complejidad de skeletons; el spinner es más simple y honesto.
- **Renderizar checkbox/botón deshabilitados hasta que `texto` llegue**: menos confuso que el bug actual, pero igual muestra el botón. Mejor no mostrar nada.

**Trade-off aceptado**: el alumno ve un instante de spinner en la primera carga. Es aceptable — es lo correcto frente a la confusión actual.

### D3 — Botón "volver" consistente

**Decisión**: crear un componente `BackButton` (o función helper) en `frontend/src/ui/components.tsx` que renderice un botón con `<Icon name="arrow_back" />` + label "Volver", visible en la parte superior izquierda de la pantalla. Recibe un `onClick` que navega al paso anterior del workflow (configurable por screen).

Patrón visual: igual al ya usado en `Consent.tsx:171-178` "Volver a la confirmación rápida" pero generalizado y como componente.

**Alternativas consideradas**:
- **Botón del navegador del browser**: no funciona consistente con SPA + lógica de step (el browser back puede saltar steps).
- **Hardcoded en cada screen**: perpetúa inconsistencia.

**Trade-off aceptado**: 1 componente más. Compensa por consistencia visual.

### D4 — Layout desktop del `StudentShell`

**Decisión**: el `StudentShell` mantiene su `max-width` actual (`max-w-3xl` o lo que tenga) pero las pantallas internas pueden romper esa restricción cuando lo necesiten (ej. consent en grid 2-columnas en desktop). Estrategia: usar `lg:max-w-5xl` o `xl:max-w-6xl` en el shell para desktop, y dentro de las pantallas usar grids responsive (`grid sm:grid-cols-2 lg:grid-cols-3`).

**Alternativas consideradas**:
- **Quitar `max-width` completo**: el contenido se hace ilegible en pantallas 4K (líneas muy largas).
- **Layout full-width con sidebar**: cambio mucho más grande, fuera del scope de este change.

**Trade-off aceptado**: solución intermedia. Más adelante (no en c-66) se puede evaluar un layout con sidebar si hace falta.

### D5 — Card amarilla "Completá tu perfil" como hero del dashboard

**Decisión**: el componente del dashboard del estudiante (probablemente `StudentDashboard.tsx`) hace un check del estado del enrollment:
- Si `enrollment.perfil_completo === false` → render del header + saludo + identificación + card amarilla con CTA `<Button>Completar perfil</Button>` que navega a `/consent` o el step pendiente.
- Si `enrollment.perfil_completo === true` → render del header + saludo + identificación + UI normal del dashboard (lista de exámenes habilitados, etc.).

El card amarillo usa el patrón existente de `Card` con `bg-warning-container` (token de design system; verificar nombre exacto en `components.tsx`) + icono ⚠️ + título + descripción de qué falta + CTA.

**Alternativas consideradas**:
- **Toast/banner en la parte superior**: menos jerarquía visual, fácil de ignorar.
- **Modal bloqueante**: agresivo, mala UX.

**Trade-off aceptado**: card visible como hero (lo que pidió el dueño con la captura) es la mejor jerarquía.

## Risks / Trade-offs

- **[Riesgo] El bug fix de `Consent.tsx` rompe deep-links que asumían la UI inmediata** → **Mitigación**: el `useEffect` carga el texto al montar; con conexión normal el spinner aparece <500ms. No hay deep-link público que asuma UI inmediata.
- **[Riesgo] Cambiar el layout desktop puede romper tests de regresión visual existentes (si los hay)** → **Mitigación**: ejecutar `npm run dev` y verificar manualmente cada pantalla afectada. No hay tests E2E Cypress/Playwright actualmente para el flujo del estudiante.
- **[Riesgo] El componente `LoadingSpinner` reutilizable puede colidir con otros spinners pre-existentes en otras pantallas (proctor/admin)** → **Mitigación**: c-66 SOLO modifica las pantallas del estudiante. Proctor/admin spinners quedan como están. Si se quiere unificar en todo el sistema, será un change futuro separado.
- **[Trade-off] Una iteración más sobre `StudentShell` puede mover la goalpost para futuros changes de UI** → Aceptado: el dueño tiene visibilidad clara sobre qué está pasando en el frontend y c-66 es una corrección focalizada de bugs visuales, no un rediseño.
- **[Riesgo] El componente `BackButton` no contempla todos los casos de navegación (ej. cuando el estudiante entra a `/consent` desde el dashboard vs desde el deep-link)** → **Mitigación**: el `onClick` del `BackButton` es configurable por screen, así cada screen decide a dónde vuelve.

## Open Questions

- **Q1**: ¿El componente `LoadingSpinner` debe respetar el `prefers-reduced-motion` del usuario? — Recomendación: sí (`@media (prefers-reduced-motion: reduce) { .ae-spin { animation: none } }`), si no está ya en el CSS global. Verificar `tailwind.config.js` / global stylesheet.
- **Q2**: ¿El card amarillo de "Completá tu perfil" debe persistir en el header de TODAS las pantallas del estudiante (hasta que complete) o solo en el dashboard? — Recomendación: solo en el dashboard. En las pantallas intermedias del workflow ya es obvio que estás completando el perfil.
- **Q3**: ¿El `BackButton` se muestra también en el dashboard del estudiante? — Recomendación: NO. El dashboard es la "raíz" del workflow del estudiante. Si necesita salir, usa el logout del header. `BackButton` aparece solo en pantallas intermedias del workflow.
