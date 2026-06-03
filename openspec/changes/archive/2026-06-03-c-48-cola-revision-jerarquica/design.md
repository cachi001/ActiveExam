## Context

Post-C-47, `Revisor.tsx` es una lista plana: `api.listarSesionesProctoring()` → filtro `score >= 60` → orden por score → `grid lg:grid-cols-3` (cola lateral + panel de detalle). El join del catálogo (`joinExamInfo`) ya existe y resuelve `exam_id → EXAMENES → COMISIONES → MATERIAS`. El store ya tiene `decisionesRevisor` / `setDecisionRevisor` / `setProctoringSessionId`. El detalle completo vive en `ProctoringSessionDetail` (`/admin/proctoring-session-detail`).

El catálogo demo es chico: una sola materia rendible (`MAT-AMAT` "Análisis Matemático I"), comisión `COM-AMAT-1A`, examen `EXAMEN_RENDIBLE_ID` (`EX-FRM-AMAT-I`). Por eso el drill-down, en mock, tendrá un único camino materia→comisión→examen con varias personas en la hoja. Eso es suficiente para demostrar la navegación; con datos reales de varias materias/comisiones la jerarquía se ramifica sola.

Restricciones:
- **Dual-mode**: `USE_REAL_BACKEND=0` → mock; el mock debe tener 2-3 sesiones de riesgo sobre el mismo examen para que la hoja "Personas" tenga contenido.
- **No buildear, no commitear** sin pedido explícito.
- **L2.5**: el score prioriza/ordena, nunca sanciona; decisión humana obligatoria.
- **Ley 25.326**: ningún nivel lista `screenshot_base64`.
- **UI limpia**: nada `absolute` sobre el texto; flex/grid con gaps; breadcrumb en su propia fila; sin solapamientos a 1440/1280/1024px.
- **Límite de líneas**: cada archivo ≤ 400; `Revisor.tsx` ≤ 400.
- **Sin códigos C-NN ni "L2.5" en texto visible**; sin `window.confirm`/`alert`; sin nombres de repos externos.

## Goals / Non-Goals

**Goals:**
- Drill-down de 4 niveles (Materia → Comisión → Examen → Persona) con breadcrumb clickable y botón volver.
- Contador "N en riesgo" en cada nodo de nivel 1-3.
- Nivel persona: una card por sesión (= persona) con score/eventos/discrepancias + acción "ver detalle".
- Detalle reusa `ProctoringSessionDetail`; panel de decisión con 3 botones en palabras llanas.
- Agregación pura, testeable, fuera del componente.
- Layout limpio sin solapamientos a 1440/1280/1024px.

**Non-Goals:**
- Endpoint backend para decisiones (no existe en el slim; se registra en store).
- Filtros adicionales (fecha, score variable) — el umbral es fijo.
- Paginación / virtualización (volumen demo bajo).
- Cambiar `ProctoringRevisor` (Sesiones grabadas) ni `Proctor` (En vivo) — fuera de alcance.

## Decisions

### D1: Estado de navegación local con un "path" de drill-down

`Revisor.tsx` mantiene `const [path, setPath] = useState<{ materia?: string; comision?: string; examen?: string }>({})`. El nivel actual se deriva: sin `materia` → nivel 1; con `materia` sin `comision` → nivel 2; con `comision` sin `examen` → nivel 3; con `examen` → nivel 4 (personas). El detalle de persona NO es un nivel del path: navega a `ProctoringSessionDetail` vía router (igual que las otras pantallas). El breadcrumb se arma del `path`.

Alternativa descartada: una máquina de estados con enum de nivel — el objeto path es más simple y el nivel se deriva sin estado redundante.

### D2: Agregación pura en `colaAgregacion.ts`

Módulo nuevo `screens/proctoring/colaAgregacion.ts`, sin React, sin hooks:

```typescript
export interface NodoCola { clave: string; nombre: string; enRiesgo: number; }
export interface SesionEnriquecida { sesion: SesionProctoringResumen; info: ExamInfo | null; }

export function enriquecerYFiltrar(sesiones, umbral): SesionEnriquecida[]
export function materiasEnRiesgo(items): NodoCola[]
export function comisionesEnRiesgo(items, materiaNombre): NodoCola[]
export function examenesEnRiesgo(items, materiaNombre, comisionNombre): NodoCola[]
export function personasEnRiesgo(items, materiaNombre, comisionNombre, examNombre): SesionEnriquecida[]
```

Cada función agrupa/cuenta sobre el array ya enriquecido (`joinExamInfo` aplicado una vez). Las sesiones sin `info` (sin `exam_id` resoluble) se agrupan bajo un nombre sentinela "Sin examen asociado" en nivel materia, propagado en cada nivel para que el drill-down no las pierda. La clave de cada nodo usa el nombre (suficiente para la demo; nombres únicos por nivel en el catálogo).

Alternativa descartada: agrupar en el componente con `useMemo` inline — infla `Revisor.tsx` y no es testeable aislado.

### D3: Componente genérico de nivel `ColaNivelGrid` + `ColaNivelCard`

Niveles 1-3 comparten estructura (grid de cards con título, contador "N en riesgo", click para bajar). Un solo componente `ColaNivelGrid` recibe `{ titulo, sub, nodos: NodoCola[], icono, onSelect }` y renderiza un `grid` responsive de `ColaNivelCard`. Esto evita 3 componentes casi idénticos. Cada `ColaNivelCard` es un `<button>` accesible con la card del design system (Card padding, Badge con el contador).

Grid responsive: `grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md` — columnas que colapsan limpio a 1024px. NADA `absolute`.

### D4: `ColaNivelPersonas` — hoja del drill-down

Recibe `{ items: SesionEnriquecida[], onAbrir }`. Renderiza una lista (stack vertical `space-y-sm`) de cards de persona: etiqueta + score badge + métricas (eventos, discrepancias) + botón "Ver detalle". El botón "Ver detalle" llama `onAbrir(sesion)` que en `Revisor.tsx` hace `setProctoringSessionId` + navigate. El panel de decisión (`ColaPanelDecision`) se muestra debajo o inline por persona seleccionada — ver D6.

### D5: `ColaBreadcrumb` en su propia fila

Componente `ColaBreadcrumb` recibe `{ path, onNavigate }`. Renderiza una fila `flex items-center flex-wrap gap-base` con segmentos clickables ("Materias" raíz › Materia › Comisión › Examen) separados por un icono chevron. Cada segmento previo es un `<button>` que llama `onNavigate(nivel)` recortando el path. El último segmento (actual) no es clickable. La fila vive ARRIBA del contenido del nivel, separada por su propio bloque — sin superposición.

### D6: Panel de decisión `ColaPanelDecision` en el nivel persona

En el nivel 4, al seleccionar una persona (estado `personaSelId`), debajo de la lista aparece `ColaPanelDecision` con la sesión seleccionada: 3 botones en palabras llanas — "Sin observaciones", "Aprobar con nota", "Enviar a revisión formal" — más un texto que aclara que el sistema solo prioriza y la decisión es del revisor. Al resolver, llama `setDecisionRevisor(id, decision)`, toast de confirmación, y quita la persona de la vista. El botón "Ver detalle completo" navega a `ProctoringSessionDetail`.

Las etiquetas de decisión se mapean a los valores del tipo `DecisionRevisor` existente (`sin_hallazgos` / `aprobado` / `flaggeado_para_sumario`). El texto visible usa palabras llanas, sin códigos.

### D7: Mock — 2-3 personas de riesgo sobre el mismo examen

En `api.ts`, `listarSesionesProctoring()` mock ya tiene una sesión score 72 sobre `EXAMEN_RENDIBLE_ID`. Se agregan 2 sesiones más de riesgo (score 84 y 67) con el mismo `exam_id` y etiquetas distintas ("Persona A — banca 12", etc., en palabras llanas, sin PII real) para que el nivel persona muestre 3 tarjetas. Las sesiones de bajo score (12, 38) se conservan y quedan fuera por el filtro.

### D8: Layout sin solapamientos — reglas concretas

- Contenedor raíz: `space-y-lg` (vertical rhythm).
- Header en su bloque; breadcrumb en su propio bloque debajo del header; contenido del nivel en su bloque.
- Grids con `gap-md`/`gap-lg`; cards con `p-lg`. Sin `position: absolute` para texto ni badges sobre contenido.
- Badges de contador dentro del flujo de la card (flex), no flotando.
- Verificación obligatoria en browser a 1440x1000 y 1280x800 (y razonar 1024).

## Risks / Trade-offs

- **[Riesgo] Catálogo demo de una sola materia** → el drill-down en mock tiene un único camino. Mitigación: es esperado; con datos reales se ramifica. La hoja "Personas" tiene 3 tarjetas, que es lo que demuestra el valor. Documentado.
- **[Riesgo] Sesiones sin `exam_id`** → caen en "Sin examen asociado". Mitigación: grupo sentinela explícito, no se pierden.
- **[Trade-off] Decisiones en store, no persistidas** → igual que C-47; aceptable en demo.
- **[Riesgo] Reescritura de `Revisor.tsx`** → el comportamiento de fuente de datos y filtro se conserva; solo cambia la presentación. Rollback: restaurar la versión plana de C-47.

## Migration Plan

1. Agregar 2 sesiones de riesgo al mock de `listarSesionesProctoring()` en `api.ts` (aditivo).
2. Crear `colaAgregacion.ts` (módulo puro nuevo).
3. Crear `ColaBreadcrumb.tsx`, `ColaNivelGrid.tsx`, `ColaNivelPersonas.tsx`, `ColaPanelDecision.tsx`.
4. Reescribir `Revisor.tsx` como orquestador de drill-down usando los nuevos componentes.
5. `tsc --noEmit` = 0; verificación browser sin solapamientos a 1440/1280.

Rollback: el paso 1 es aditivo; los pasos 2-4 son la reescritura — revertir es restaurar el `Revisor.tsx` plano y borrar los componentes nuevos.

## Open Questions

- ¿El backend real agrupa sesiones por examen? No; la agregación es del cliente sobre el join local. Asumido y correcto para la demo.
