## Context

El portal del alumno (Login + 3 pantallas) fue construido de forma incremental durante C-21, C-26, C-29, C-31 y C-40. Cada change sumó lógica inline directamente en las pantallas sin extraer componentes. El resultado actual:

| Pantalla | Líneas | Problema principal |
|---|---|---|
| Login.tsx | 72 | Estructura correcta; requiere ajuste visual menor (whitespace, jerarquía) |
| AlumnoDashboard.tsx | 168 | Accesos rápidos y cards de examen repetidos inline; sin componentes |
| AlumnoMaterias.tsx | 264 | Árbol Materia→Comisión→Examen completamente inline; 3 niveles de JSX anidado |
| AlumnoMisExamenes.tsx | 230 | Card de inscripción con gate en capas (C-26) toda inline |

El design system (tailwind.config.js + `ui/components.tsx`) ya define todas las primitivas necesarias: `Card`, `Badge`, `Button`, `Icon`, `SectionTitle`. No se requieren nuevos tokens ni primitivas.

## Goals / Non-Goals

**Goals:**
- Extraer 6 componentes de presentación desde las 3 pantallas monolíticas
- Reducir cada pantalla a ≤ 120 líneas (orquestador de estado + composición de componentes)
- Aplicar jerarquía visual clara: más whitespace, badges de estado prominentes, botones de tamaño correcto
- Refinar Login con layout minimalista centrado y branding UTN FRM legible
- Mantener 100% de compatibilidad con la lógica de negocio existente (inscripción, gate C-26, acuse C-26, navegación)
- PascalCase en archivos y componentes; reuso de design system

**Non-Goals:**
- Cambiar la lógica de estado, llamadas a `api.ts`, tipos de `types.ts` o el store de Zustand
- Modificar `shells.tsx`, `components.tsx`, `AcuseExamen.tsx`, `router.tsx`
- Agregar animaciones o micro-interacciones nuevas más allá de las ya provistas por Tailwind
- Implementar storybook, design tokens nuevos o dark mode
- Cambiar el flujo de autenticación o las rutas

## Decisions

### D1 — Directorio de componentes: `frontend/src/screens/alumno/components/`

**Decisión**: los 6 nuevos componentes van en un subdirectorio `components/` dentro de `screens/alumno/`.

**Alternativa considerada**: `frontend/src/ui/alumno/` (junto al design system global).

**Rationale**: los componentes son específicos del dominio alumno — conocen los tipos `Inscripcion`, `Examen`, `Materia`, `Comision`. No son primitivas genéricas; pertenecen al dominio, no al design system. El directorio `ui/` es para primitivas agnósticas de dominio.

---

### D2 — Componentes de presentación pura (props → JSX, sin estado propio de app)

**Decisión**: cada componente recibe todos sus datos via props y emite callbacks para acciones. No llaman a `api` ni usan `useApp`. 

**Rationale**: separa responsabilidades. La pantalla gestiona el estado; el componente renderiza. Facilita tests unitarios de UI sin mocks de store.

**Implicación**: `InscripcionCard` recibe `gate`, `verificando`, `onRendir`, `onCompletarAcuse` como props; no evalúa el gate internamente.

---

### D3 — Login: refinamiento visual sin reescritura

**Decisión**: no reestructurar el JSX del Login (ya limpio post C-29/C-40). Solo ajustar:
- Logo: agregar `INSTITUTION.sigla` debajo del ícono (UTN FRM visible)
- Aumentar el `gap` entre secciones para más aire
- Microcopy de privacidad: condensar a una sola línea (ya es label-sm)
- El botón CTA ya tiene `size="lg"` y `w-full` — no cambia

**Rationale**: el Login tiene 72 líneas y una sola responsabilidad. No hay componentización necesaria. El cambio es cosmético y de bajo riesgo.

---

### D4 — `MateriaCard` encapsula el acordeón completo (incluyendo `ComisionRow`)

**Decisión**: `MateriaCard` renderiza el encabezado de la materia + el contenido expandible (que incluye la lista de `ComisionRow`). `ComisionRow` a su vez incluye la lista de `ExamenCard`.

**Alternativa considerada**: aplanar en 3 componentes sin composición (pasar listas via props).

**Rationale**: el acordeón anidado es cohesivo — `MateriaCard` necesita saber sus comisiones para renderizarlas cuando está activa. La composición Materia→Comisión→Examen es un árbol natural; los 3 componentes están acoplados por diseño.

---

### D5 — `ExamenCard` recibe el estado de inscripción como prop booleano

**Decisión**: `ExamenCard` recibe `inscripto: boolean`, `inscribiendo: boolean` y `onInscribir: () => void` como props. No conoce la lista completa de inscripciones.

**Rationale**: desacopla la lógica de consulta (`estaInscripto(examen.id)`) de la presentación. La pantalla `AlumnoMaterias` sigue siendo quien calcula `estaInscripto`.

---

### D6 — Grilla responsive en accesos rápidos del Dashboard

**Decisión**: `QuickAccessCard` usa `grid-cols-1 sm:grid-cols-2 gap-md` igual que hoy, pero el componente encapsula la visual de cada ítem (ícono + título + descripción + flecha).

**Rationale**: elimina los 3 bloques `<button>` idénticos inline en AlumnoDashboard (actualmente ~40 líneas de repetición).

## Risks / Trade-offs

**[Riesgo: romper el gate C-26 al mover lógica a InscripcionCard]** → Mitigación: `InscripcionCard` es presentación pura; toda la lógica del gate (`codigoGate`, `puedeRendirEsteExamen`, `setExamenCompletandoAcuse`) permanece en `AlumnoMisExamenes` y se pasa como props. No se mueve lógica, solo JSX.

**[Riesgo: over-engineering — componentes que se usan una sola vez]** → Mitigación: todos los componentes extraídos aparecen al menos 2 veces (`QuickAccessCard` × 3, `ExamenProximoCard` × N inscripciones, `MateriaCard` × N materias, `ExamenCard` × N exámenes, `InscripcionCard` × N inscripciones). `ComisionRow` aparece × N comisiones. Ninguno es singleton.

**[Trade-off: más archivos en el repo]** → Aceptado. La legibilidad de 6 pantallas finas supera el overhead de 6 archivos adicionales. Los archivos son pequeños (30–60 líneas cada uno).

**[Riesgo: regresión visual en Login]** → Mitigación: el Login ya funciona post C-29/C-40. Los cambios son aditivos (más whitespace, ajuste de gap); no se remueve nada funcional.

## Migration Plan

1. Crear directorio `frontend/src/screens/alumno/components/`
2. Crear los 6 componentes (presentación pura; no rompen nada al existir)
3. Refactorizar `AlumnoDashboard.tsx` usando `QuickAccessCard` y `ExamenProximoCard`
4. Refactorizar `AlumnoMaterias.tsx` usando `MateriaCard`, `ComisionRow`, `ExamenCard`
5. Refactorizar `AlumnoMisExamenes.tsx` usando `InscripcionCard`
6. Ajustar `Login.tsx` (cambios visuales menores)
7. Verificar en navegador que los 4 flujos funcionan: login → dashboard, ver materias → inscribir, mis exámenes → rendir / completar acuse

Sin rollback plan especial — es refactor de UI pura. En caso de regresión, revertir commits individuales por pantalla.

## Open Questions

- ¿Se agrega un `index.ts` de barrel export en `alumno/components/`? (Decisión de estilo; se puede decidir durante apply sin bloquear el diseño.)
- ¿`ExamenProximoCard` en el Dashboard debe mostrar un link directo a "Rendir" si está habilitado? (Requeriría evaluar el gate desde el Dashboard — actualmente solo muestra `puedeRendir` global, no por-examen.) → Mantener comportamiento actual (sin CTA de rendir en Dashboard); el usuario va a "Mis exámenes" para eso.
