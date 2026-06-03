## Why

El proyecto tiene tres pantallas para el rol staff que conviven en el área de proctoring, pero ninguna de ellas tiene una identidad clara ni un propósito diferenciado desde el punto de vista del usuario:

- **`Revisor.tsx`** — llamada "Cola de revisión humana" — opera **completamente con datos mock** (`api.reviewQueue()` / `COLA_REVISION`): muestra sesiones hardcodeadas con foto de alumno, nombre, eventos ficticios y un panel de decisión que escribe en memoria. No está conectada al backend slim C-45/C-46.
- **`ProctoringRevisor.tsx`** — "Sesiones grabadas" — ya conectada al backend real (C-46): lista el historial COMPLETO de sesiones (`listarSesionesProctoring()`), sin filtrar por propósito ni score. No tiene subtítulo que explique qué muestra.
- **`Proctor.tsx`** — "Supervisión en vivo" — ya hace polling real (C-46): muestra TODAS las sesiones ordenadas por score, pero no filtra por estado "activo/en curso" ni deja claro al operador qué debe hacer ante una sesión en pantalla.

El resultado es confuso: hay tres vistas que parecen variantes de lo mismo sin diferenciación funcional. La "Cola de revisión" es la pantalla más crítica del flujo L2.5 (priorización para decisión humana), pero sigue siendo mock. Nadie puede distinguir en qué se diferencia una sesión "en cola" de una "grabada" de una "en vivo".

Este change cierra ese gap: diferencia las tres pantallas con identidades claras, conecta `Revisor.tsx` al backend real con filtro de alto riesgo, enriquece cada sesión de cola con los datos de contexto académico (examen/materia/comisión joineado desde el catálogo local via `exam_id`), y agrega la acción de resolución humana real. `ProctoringRevisor` recibe un subtítulo que la identifica como historial completo. `Proctor` recibe filtro visual por estado activo para que el operador sepa exactamente qué está ocurriendo ahora.

## What Changes

- **`Revisor.tsx`** (Cola de revisión): reemplazar `api.reviewQueue()` (mock) por `api.listarSesionesProctoring()` real con filtro `score >= UMBRAL_COLA` (default 60). Join de `exam_id` → `EXAMENES / COMISIONES / MATERIAS` del catálogo local para mostrar materia, docente, comisión. Detalle completo al click: reusar `ProctoringSessionDetail` (ruta `/admin/proctoring-session-detail`). Acción de resolución humana: botón con estado de decisión (`aprobado` / `flaggeado_para_sumario` / `sin_hallazgos`) que escribe un registro local de la decisión del revisor (sin endpoint — el backend slim no tiene tabla de decisiones; L2.5 exige registro, no automatización). Score umbral configurable en `INSTITUTION` o como constante local.
- **`ProctoringRevisor.tsx`** (Sesiones grabadas): agregar subtítulo que aclare el propósito ("Historial completo de sesiones de proctoring grabadas — todas, sin filtro") y un tag/badge de conteo total. Join de `exam_id` al mostrar cada `SesionCard` para enriquecer con nombre de examen/materia cuando esté disponible.
- **`Proctor.tsx`** (Supervisión en vivo): agregar sección "Activas ahora" que filtre sesiones con `modo === 'examen'` (o una heurística de reciente actividad: `creada_en` en los últimos N minutos) separadas visualmente de sesiones de diagnóstico. Subtítulo que deje claro qué acción tomar ("Intervenir" / "Ver detalle"). El click en una sesión activa lleva al detalle (`ProctoringSessionDetail`) — ya funciona, solo necesita la diferenciación visual.
- **`SesionCard.tsx`** y **`SesionVivoCard.tsx`** (componentes en `screens/proctoring/`): enriquecer props para aceptar opcionalmente `examNombre` / `materiaNombre` / `comisionNombre` joineados desde el catálogo local. No rompen el contrato existente (props opcionales).
- **`helpers.ts`** (`screens/proctoring/`): agregar función pura `joinExamInfo(examId: string | undefined): ExamInfo | null` que busca en EXAMENES → COMISIONES → MATERIAS del catálogo local y retorna un objeto `{ examNombre, materiaNombre, comisionNombre, docente } | null`. La función es pura (no llama a `api`, opera sobre los arrays locales importados).
- **Constante `UMBRAL_COLA_REVISION`**: definida en `helpers.ts` o en la propia pantalla `Revisor.tsx` (valor default: 60). Documentada como "score mínimo para que una sesión aparezca en la cola de revisión priorizada".
- **Tipos locales de decisión**: `type DecisionRevisor = 'aprobado' | 'flaggeado_para_sumario' | 'sin_hallazgos' | 'pendiente'`. Se define en `types.ts`. El registro de decisión se guarda en el store (estado local de la sesión) — no hay endpoint en el backend slim para esto; la decisión es del revisor, la plataforma la registra localmente para la demo.

## Capabilities

### New Capabilities
- `cola-revision-real`: `Revisor.tsx` conectada al backend real con filtro de alto riesgo, join de catálogo, acción de resolución humana. Diferencia semántica clara entre "Cola" (prioridad alta, pendientes de decisión) vs "Grabadas" (historial) vs "En vivo" (activas ahora).
- `exam-catalog-join`: función pura `joinExamInfo` en `helpers.ts` que enriquece cualquier sesión con datos del catálogo local (examen/materia/comisión) a partir del `exam_id`. Reutilizable en las tres pantallas.
- `decision-revisor-local`: tipo `DecisionRevisor` + acción de resolución en la Cola de revisión — registro local de la decisión humana (sin endpoint backend); L2.5 compliant.

### Modified Capabilities
- `proctoring-revisor-real` (C-46): agrega subtítulo de propósito + join de catálogo en `ProctoringRevisor.tsx`.
- `proctor-live-panel` (C-43/C-46): agrega diferenciación visual por estado (activo/diagnóstico) en `Proctor.tsx`.
- `session-card-components` (C-46): enriquece `SesionCard` y `SesionVivoCard` con props opcionales de contexto académico.

## Impact

- **Archivos modificados**: `frontend/src/screens/Revisor.tsx`, `frontend/src/screens/ProctoringRevisor.tsx`, `frontend/src/screens/Proctor.tsx`, `frontend/src/screens/proctoring/SesionCard.tsx`, `frontend/src/screens/proctoring/SesionVivoCard.tsx`, `frontend/src/screens/proctoring/helpers.ts`, `frontend/src/lib/types.ts`
- **Archivos nuevos**: ninguno — todo el trabajo es extensión/refinamiento de componentes existentes.
- **Dependencia**: backend slim C-45/C-46 en Railway; sin `USE_REAL_BACKEND=1` todo opera en mock (dual-mode intacto).
- **L2.5**: la Cola de revisión muestra sesiones priorizadas pero la plataforma NUNCA sanciona. El panel de resolución registra la decisión del revisor humano; el score es un acumulador de priorización, no un veredicto.
- **Ley 25.326**: la cola de revisión no lista `screenshot_base64` en la lista — solo en el detalle (ya manejado por `ProctoringSessionDetail`). El join del catálogo es metadata académica, no dato sensible adicional.
- **Sin breaking changes**: todas las modificaciones a componentes son aditivas (props opcionales). `Revisor.tsx` cambia su fuente de datos de mock a real; el mock sigue disponible via `USE_REAL_BACKEND=0`.
