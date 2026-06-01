## Why

La UI expone jerga técnica y legal cruda al usuario final (alumno, admin, revisor) sin ninguna explicación: "L2.5", "embedding", "WORM", "liveness", "cadena de custodia", "Face Mesh". Esta terminología es indispensable —por precisión legal y técnica— pero incomprensible para el 99 % de los usuarios. El resultado es desconfianza, consultas de soporte y riesgo de que el usuario no entienda qué está aceptando (Ley 25.326, base legal del consentimiento informado).

**¿Por qué ahora?** Los changes C-21..C-27 consolidaron la capa de presentación y crearon el patrón de config central (`institution.ts`). Es el momento justo para agregar inteligibilidad sin romper nada: todas las menciones están en el frontend ya implementado, hay un patrón de `config/` establecido, y no hay backend involucrado.

## What Changes

- **Nuevo módulo** `frontend/src/config/glossary.ts`: diccionario central `Record<string, GlossaryEntry>` con definición en lenguaje claro y referencia legal opcional para cada término técnico visible al usuario. Fuente única de verdad; jamás inline en los componentes.
- **Nuevo componente átomo** `frontend/src/ui/Term.tsx`: envuelve texto técnico con tooltip accesible (hover en desktop, tap en mobile), aria-describedby, y el texto de la definición del glosario. PascalCase, reutilizable, cero dependencias externas.
- **Reemplazo de menciones crudas** en los archivos de mayor impacto al alumno: las 19 menciones de "L2.5", las 4 de "embedding", y las ocurrencias de "WORM", "liveness", "cadena de custodia" y "Face Mesh" más visibles para el usuario. El término técnico queda visible; la definición aparece al interactuar.
- **Vista de glosario completo** (opcional): panel/modal accesible desde un icono "?" en el footer o en pantallas clave (AcuseExamen, Consent), que lista todos los términos del diccionario.

## Capabilities

### New Capabilities

- `glossary-config`: Módulo central `frontend/src/config/glossary.ts` con el diccionario de términos técnicos (tipo, definición, referencia legal opcional). Fuente única de verdad para `<Term>`.
- `term-tooltip-component`: Componente átomo `<Term>` en `frontend/src/ui/Term.tsx` que envuelve cualquier texto técnico con su definición accesible (tooltip/popover responsive, aria, touch-friendly).
- `glossary-panel`: Vista opcional de glosario completo (modal o page), accesible desde el footer o desde un icono contextual "?". Lista todos los términos del diccionario con sus definiciones.

### Modified Capabilities

- `institution-config`: El patrón de módulo en `frontend/src/config/` se extiende con `glossary.ts` siguiendo la misma convención (módulo TypeScript puro, export named, sin reactividad). No cambia el contrato de `institution.ts`, solo se establece la convención de la carpeta `config/` como punto de extensión canónico.

## Impact

- **Archivos nuevos**: `frontend/src/config/glossary.ts`, `frontend/src/ui/Term.tsx`, `frontend/src/ui/GlossaryPanel.tsx` (si se implementa la vista completa).
- **Archivos modificados** (menciones crudas → `<Term>`):
  - `frontend/src/screens/AdminDashboard.tsx` (L2.5 ×1)
  - `frontend/src/screens/Reports.tsx` (L2.5 ×1)
  - `frontend/src/screens/Revisor.tsx` (L2.5 ×1, cadena de custodia ×1)
  - `frontend/src/screens/StudentProfile.tsx` (L2.5 ×2, embedding ×1)
  - `frontend/src/screens/AdminDetectionHarness.tsx` (L2.5 ×2)
  - `frontend/src/screens/AcuseExamen.tsx` (L2.5 ×1)
  - `frontend/src/screens/Cierre.tsx` (L2.5 ×1)
  - `frontend/src/screens/Examen.tsx` (cadena de custodia ×1)
  - `frontend/src/screens/SessionDetail.tsx` (cadena de custodia ×1)
  - `frontend/src/screens/Biometria.tsx` (liveness ×1)
  - `frontend/src/features/enrollment/EnrollmentBiometricStep.tsx` (liveness ×2, L2.5 ×1)
  - `frontend/src/features/enrollment/BiometricRenewalStatus.tsx` (L2.5 ×1)
  - `frontend/src/features/consentimiento/ConsentScreen.tsx` (embedding ×1, WORM ×1)
  - `frontend/src/screens/Consent.tsx` (embedding ×1)
  - `frontend/src/features/enrollment/EnrollmentConsentStep.tsx` (embedding ×1)
  - `frontend/src/lib/api.ts` (L2.5 ×1 — comentario/descripción visible al dev)
- **Sin impacto en**: backend, contratos de API, BD, lógica de negocio, tests de integración. Cambio 100 % en la capa de presentación.
- **Sin dependencias de backend**: C-28 es independiente; puede correrse en cualquier momento sobre la rama de refinamiento (igual que C-27).
