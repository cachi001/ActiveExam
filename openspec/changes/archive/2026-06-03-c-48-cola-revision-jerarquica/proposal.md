## Why

El C-47 conectó la Cola de revisión (`Revisor.tsx`) al backend real, pero lo hizo con un **modelo plano**: una sola lista lateral de sesiones de alto riesgo + un panel de detalle. Ese diseño tiene dos problemas concretos:

1. **No escala cognitivamente.** Un revisor de una institución con varias materias, comisiones y exámenes recibe una lista plana sin estructura. No puede responder "¿qué materia tiene más sesiones en riesgo?" ni "¿cuántas personas en riesgo hay en este examen puntual?" sin escanear ítem por ítem. La organización académica real (materia → comisión → examen → persona) se pierde.
2. **La UI quedó solapada.** El layout de dos columnas (`grid lg:grid-cols-3`) con cards y elementos posicionados encima del texto produce solapamientos visuales a 1280px y 1024px. El usuario reportó que la pantalla quedó "toda sobrepuesta".

Este change REEMPLAZA el modelo plano del C-47 por una **navegación drill-down jerárquica** que sigue la estructura académica natural y un layout limpio (flex/grid con gaps claros, sin `absolute` sobre el texto), verificado sin solapamientos a 1440px, 1280px y 1024px.

## What Changes

- **`Revisor.tsx`** pasa de lista plana a **orquestador de drill-down** de 4 niveles con breadcrumb clickable:
  - **Nivel 1 — Materias**: cards de las materias que tienen sesiones EN RIESGO (`score >= UMBRAL_COLA_REVISION`), cada una con contador "N en riesgo".
  - **Nivel 2 — Comisiones**: al hacer click en una materia, sus comisiones con sesiones en riesgo, cada una con "N en riesgo".
  - **Nivel 3 — Exámenes**: al hacer click en una comisión, sus exámenes con sesiones en riesgo, cada uno con "N en riesgo".
  - **Nivel 4 — Personas en riesgo**: al hacer click en un examen, las sesiones de proctoring de ese examen con `score >= UMBRAL` (cada sesión = una persona), mostrando score / eventos / discrepancias.
  - **Detalle + decisión**: al hacer click en una persona, se reusa `ProctoringSessionDetail` (navegación a `/admin/proctoring-session-detail`) y se ofrece el panel de decisión del revisor (3 botones, palabras llanas).
  - **Breadcrumb** (Materia › Comisión › Examen) en su propia fila, clickable para volver a cualquier nivel, más botón "Volver".
- **Agregación jerárquica** pura sobre el join del catálogo: las sesiones reales (`api.listarSesionesProctoring()`, dual real/mock) se filtran a riesgo alto y se agrupan por `materiaNombre` → `comisionNombre` → `examNombre` usando `joinExamInfo` (`screens/proctoring/helpers.ts`, ya existe). Sesiones sin `exam_id` resoluble caen en un grupo "Sin examen asociado".
- **Componentización** en `screens/proctoring/`: un componente genérico de nivel (`ColaNivelGrid` + `ColaNivelCard`) reutilizado por los niveles 1-3, un componente de personas (`ColaNivelPersonas`), el breadcrumb (`ColaBreadcrumb`) y el panel de decisión (`ColaPanelDecision`). Cada archivo ≤ 400 líneas; `Revisor.tsx` ≤ 400.
- **Mock**: se agregan 2-3 sesiones de riesgo (`score >= 60`) con `exam_id = EXAMEN_RENDIBLE_ID` y etiquetas distintas (simulando 2-3 personas) para que el drill-down tenga contenido sin backend.

## Capabilities

### New Capabilities
- `cola-revision-jerarquica`: navegación drill-down de 4 niveles (Materia → Comisión → Examen → Persona) con breadcrumb clickable y panel de decisión humana en el nivel persona. Reemplaza el modelo plano del C-47. Layout limpio sin solapamientos a 1440/1280/1024px.
- `agregacion-cola-por-catalogo`: función(es) pura(s) de agregación que agrupan las sesiones de alto riesgo por materia/comisión/examen usando `joinExamInfo`, con contadores "N en riesgo" por nodo.

### Modified Capabilities
- `cola-revision-real` (C-47): la fuente de datos (`listarSesionesProctoring` real/mock con filtro `score >= UMBRAL`) y el panel de decisión L2.5 se conservan; cambia la PRESENTACIÓN de lista plana a drill-down jerárquico.

## Impact

- **Archivos modificados**: `frontend/src/screens/Revisor.tsx` (reescrito como orquestador de drill-down), `frontend/src/lib/api.ts` (mock: 2-3 sesiones de riesgo extra sobre `EXAMEN_RENDIBLE_ID`).
- **Archivos nuevos**: `frontend/src/screens/proctoring/ColaBreadcrumb.tsx`, `frontend/src/screens/proctoring/ColaNivelGrid.tsx`, `frontend/src/screens/proctoring/ColaNivelPersonas.tsx`, `frontend/src/screens/proctoring/ColaPanelDecision.tsx`, `frontend/src/screens/proctoring/colaAgregacion.ts` (agregación pura).
- **Reutilización**: `joinExamInfo` (helpers.ts), `Card/Button/Badge/Icon/SectionTitle` (ui/components), `useToast` (ui/toast), store `setDecisionRevisor` / `setProctoringSessionId`. No se introducen `window.confirm`/`alert`.
- **L2.5**: el score solo prioriza y ordena la jerarquía; nunca sanciona. La decisión disciplinaria es siempre humana, registrada localmente en el store.
- **Ley 25.326**: ningún nivel de la jerarquía lista `screenshot_base64`; el dato sensible vive solo en `ProctoringSessionDetail`.
- **Sin breaking changes**: la fuente de datos y el filtro no cambian; el cambio es de presentación. El mock dual-mode sigue intacto.
