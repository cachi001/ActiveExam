## Why

Las cuatro pantallas del portal del alumno (Login, AlumnoDashboard, AlumnoMaterias, AlumnoMisExamenes) son monolíticas: mezclan layout, lógica de estado y elementos de UI repetidos inline. El resultado es código de 168–264 líneas por pantalla, sin componentes reutilizables, con botones de tamaños inconsistentes y densidad visual alta. El rediseño limpia la jerarquía visual, extrae componentes reutilizables y reduce cada pantalla a ≤ 120 líneas.

## What Changes

- **Login**: refinamiento minimalista — layout centrado, branding UTN FRM claro (logo + institución), card limpia con sombra suave, único CTA `size="lg"`, microcopy reducido. Sin cambios de flujo ni lógica.
- **AlumnoDashboard** (168 → ≤ 100 líneas): extraer `QuickAccessCard` y `ExamenProximoCard` como componentes reutilizables; pantalla queda como orquestador de datos + layout.
- **AlumnoMaterias** (264 → ≤ 120 líneas): extraer `MateriaCard` (acordeón), `ComisionRow` (acordeón anidado) y `ExamenCard` (con botón inscribir + badge estado); el árbol de selección queda composable y legible.
- **AlumnoMisExamenes** (230 → ≤ 110 líneas): extraer `InscripcionCard` (estado + badge + acción + banner gate); pantalla queda como lista simple.
- **Nuevos componentes** en `frontend/src/screens/alumno/components/`: `QuickAccessCard`, `ExamenProximoCard`, `MateriaCard`, `ComisionRow`, `ExamenCard`, `InscripcionCard`. PascalCase, props tipadas, reutilizan `Card`, `Badge`, `Button`, `Icon` del design system.
- **Sin cambios de lógica**: inscripción, gate en capas (C-26), acuse (C-26), navegación y llamadas a `api.ts` permanecen intactos.

## Capabilities

### New Capabilities

- `alumno-portal-components`: Biblioteca de componentes de presentación para el portal del alumno — `QuickAccessCard`, `ExamenProximoCard`, `MateriaCard`, `ComisionRow`, `ExamenCard`, `InscripcionCard`. Cada uno encapsula su visual y recibe props tipadas; no gestiona estado propio de la app.

### Modified Capabilities

- `login-portal-reframe`: Ajuste visual del Login — mayor whitespace, jerarquía institucional más clara (logo Material 3, nombre institución + facultad prominentes), CTA único `size="lg"`, microcopy de privacidad condensado. Sin cambio de requirement funcional, sí delta visual en la card.
- `student-dashboard-landing`: Refactor de AlumnoDashboard para usar `QuickAccessCard` y `ExamenProximoCard`. El contrato de datos (inscripciones, gate) no cambia; cambia la estructura del JSX.
- `exam-enrollment`: Refactor de AlumnoMaterias para usar `MateriaCard`, `ComisionRow`, `ExamenCard`. El flujo de selección materia → comisión → examen → acuse (C-26) no cambia; cambia la estructura visual.
- `student-portal-navigation`: Refactor de AlumnoMisExamenes para usar `InscripcionCard`. El gate en capas (C-26), el banner de bloqueo y la navegación a AcuseExamen no cambian; cambia la estructura de la card.

## Impact

- **Archivos modificados**: `frontend/src/screens/Login.tsx`, `frontend/src/screens/AlumnoDashboard.tsx`, `frontend/src/screens/AlumnoMaterias.tsx`, `frontend/src/screens/AlumnoMisExamenes.tsx`
- **Archivos creados**: `frontend/src/screens/alumno/components/QuickAccessCard.tsx`, `ExamenProximoCard.tsx`, `MateriaCard.tsx`, `ComisionRow.tsx`, `ExamenCard.tsx`, `InscripcionCard.tsx`
- **Sin impacto en**: `api.ts`, `types.ts`, `store.ts`, `router.tsx`, `shells.tsx`, `components.tsx`, `AcuseExamen.tsx`, rutas, lógica de negocio, tests de integración.
- **Design system**: se usan los tokens existentes de `tailwind.config.js` (colores Material 3, espaciado, tipografía, sombras) y las primitivas de `ui/components.tsx`. No se agregan tokens nuevos.
