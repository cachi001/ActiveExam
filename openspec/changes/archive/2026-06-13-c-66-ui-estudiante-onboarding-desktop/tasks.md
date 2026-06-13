# Tasks — C-66 `ui-estudiante-onboarding-desktop`

> Frontend-only. React + Vite + Tailwind. Sin backend, sin migraciones, sin tocar Vercel deploy config.
>
> Estrategia: empezar con el componente `LoadingSpinner` y `BackButton` (base reutilizable), luego ir screen por screen aplicándolos + arreglando bugs específicos.

## 1. Componentes base reutilizables

- [x] 1.1 Agregar `LoadingSpinner` a `frontend/src/ui/components.tsx` con prop `size` (`'sm' | 'md' | 'lg'`, default `'md'`) y `label` opcional. Usar `Icon name="progress_activity" className="ae-spin text-primary text-[XX]"` con tamaños 20/32/48. Envolver en `flex items-center justify-center py-xl gap-sm` para centrado. Done: storybook o playground muestra los 3 tamaños + con/sin label.
- [x] 1.2 Agregar `BackButton` a `frontend/src/ui/components.tsx` con prop `onClick: () => void`. Renderiza `<button>` con `<Icon name="arrow_back" />` + `Volver`, posicionado top-left del contenedor. Estilo coherente con el patrón visual existente de `Consent.tsx:171-178`. Done: componente exportado + uso de ejemplo.
- [x] 1.3 Test visual rápido: verificar en `npm run dev` que los componentes se ven correctos en mobile + desktop (sin tests automatizados — verificación manual).

## 2. Dashboard del estudiante: card amarillo + hero del onboarding

- [x] 2.1 Identificar el componente que renderiza el dashboard del estudiante (probablemente `StudentDashboard.tsx` o `Home.tsx` para rol `estudiante`). Leer su lógica actual de check de `enrollment.perfil_completo`. Done: archivo identificado y entendido.
- [x] 2.2 Implementar el render del card amarillo "Completá tu perfil antes de rendir" cuando `perfil_completo === false`. Usar `<Card>` con `bg-warning-container` (o equivalente del design system; verificar token exacto) + icono ⚠️ + título + descripción dinámica de qué falta (consentimiento, biometría, ambos) + `<Button>Completar perfil</Button>`. Done: el card aparece arriba del resto del contenido cuando aplica.
- [x] 2.3 Implementar la navegación del botón "Completar perfil": navega a `/consent` si falta consentimiento, a `/biometria` si solo falta biometría, etc. Lógica de "primer paso pendiente". Done: clic en el botón navega correctamente para los 3 casos (sin consent, sin bio, sin ambos).
- [x] 2.4 Verificar manualmente con estudiante de prueba que el primer render del dashboard muestra el card amarillo arriba sin scroll en mobile + desktop. Done: matches `captura.png`.

## 3. Botón "volver atrás" en pantallas del workflow del estudiante

- [x] 3.1 Agregar `<BackButton>` a la parte superior de `Consent.tsx` que navegue al dashboard. Done: visible y funcional.
- [x] 3.2 Agregar `<BackButton>` a `EnrollmentConsentStep.tsx`, `EnrollmentBiometricStep.tsx`, `EnrollmentDniStep.tsx` con navegación al paso anterior correspondiente. Done: cada screen tiene back button con navegación correcta.
- [x] 3.3 Confirmar que el dashboard NO tiene `<BackButton>` (es la raíz del workflow del estudiante). Done: dashboard limpio.

## 4. Layout desktop del `StudentShell`

- [x] 4.1 Leer `frontend/src/ui/shells.tsx`, identificar el `max-width` actual del `StudentShell`. Done: archivo entendido.
- [x] 4.2 Aumentar el `max-width` en breakpoints desktop: agregar `lg:max-w-5xl xl:max-w-6xl 2xl:max-w-7xl` (o ajustar según el tamaño actual). Mantener mobile sin cambios. Done: en desktop el contenido usa más ancho.
- [x] 4.3 Verificar manualmente que las pantallas internas con grids responsive (e.g. consent con `grid sm:grid-cols-2`) siguen viéndose bien con el nuevo ancho. Ajustar si hay alguna que se rompe. Done: zero regresión visual en mobile + desktop.

## 5. Fix del bug de carga en `Consent.tsx`

- [x] 5.1 Agregar early return en `Consent.tsx`: si `texto === null` retornar `<StudentShell step={2}><LoadingSpinner label="Cargando consentimiento…" /></StudentShell>`. Done: cuando texto no llegó, solo se ve el spinner.
- [x] 5.2 Verificar manualmente con throttling de red (DevTools "Slow 3G") que el botón "Acepto y continúo" no aparece antes que las cláusulas. Done: bug reproducido y corregido.
- [x] 5.3 Confirmar que el caso de la rama liviana (yaConsintioPerfil) también respeta el bloqueo — el chequeo `yaConsintioPerfil` depende de `texto.version`, entonces si `texto === null` el early return de 5.1 ya lo cubre. Done: rama liviana también funciona correctamente.

## 6. Spinner unificado en todas las pantallas del estudiante

- [x] 6.1 Reemplazar el spinner inline gris de `StudentProfile.tsx:214` (`<Icon name="progress_activity" className="ae-spin text-[24px]" /> + "Cargando perfil…"`) por `<LoadingSpinner label="Cargando perfil…" />`. Done: pantalla de carga del perfil usa spinner morado.
- [x] 6.2 Reemplazar el spinner inline gris de `EnrollmentConsentStep.tsx:165` por `<LoadingSpinner />` o ajustar inline a `text-primary`. Verificar contexto (si es spinner de pantalla o de botón). Done: consistente.
- [x] 6.3 Verificar `Consent.tsx:161` y `Consent.tsx:212` — los spinners de los botones "Registrando…" se mantienen inline (`text-[20px]`) porque son UI de botón, no de pantalla. Done: criterio respetado.
- [x] 6.4 Smoke test manual: navegar por todas las pantallas del estudiante en `npm run dev` y verificar que CADA spinner visible (de pantalla) sea morado y centrado. Done: consistencia visual confirmada.

## 7. Verificación final

- [x] 7.1 Smoke test del flujo completo del estudiante: login → dashboard (con card amarillo) → "Completar perfil" → consent (con spinner inicial, luego cláusulas + checkbox + botón juntos) → biometria → DNI opcional → dashboard final (sin card amarillo). Done: flujo end-to-end OK.
- [x] 7.2 Verificar responsive: probar el flujo completo en mobile (375x667), tablet (768x1024) y desktop (1920x1080). Ningún layout roto. Done: 3 viewports OK.
- [x] 7.3 Verificar que NO se rompió ningún flujo de proctor/admin (no debería porque c-66 es solo del estudiante, pero confirmar). Done: nada de proctor/admin afectado.
- [x] 7.4 `npm run build` exitoso sin errores TypeScript. Done: build verde.
