## 1. Mock — personas de riesgo para el drill-down

- [x] 1.1 En `frontend/src/lib/api.ts`, en el mock de `listarSesionesProctoring()`, agregar 2 sesiones de riesgo (score 84 y 67) con `exam_id: EXAMEN_RENDIBLE_ID`, `modo: 'examen'`, etiquetas distintas en palabras llanas (sin PII real), `total_eventos`/`total_discrepancias` plausibles
- [x] 1.2 Conservar la sesión existente de score 72 sobre `EXAMEN_RENDIBLE_ID` (tercera persona) y las de bajo score (12, 38) que quedan fuera por el filtro
- [x] 1.3 Verificar que las 3 sesiones de riesgo comparten `exam_id` para que `joinExamInfo` las agrupe en el mismo camino materia→comisión→examen

## 2. Agregación pura — `colaAgregacion.ts`

- [x] 2.1 Crear `frontend/src/screens/proctoring/colaAgregacion.ts` (sin React, sin hooks, sin `api` directo salvo tipos)
- [x] 2.2 Definir `interface NodoCola { clave: string; nombre: string; enRiesgo: number }` y `interface SesionEnriquecida { sesion: SesionProctoringResumen; info: ExamInfo | null }`
- [x] 2.3 Implementar `enriquecerYFiltrar(sesiones, umbral): SesionEnriquecida[]` — filtra `score >= umbral`, aplica `joinExamInfo(sesion.exam_id)` una vez, ordena por score desc
- [x] 2.4 Implementar `materiasEnRiesgo(items): NodoCola[]` — agrupa por `info.materiaNombre` (sentinela "Sin examen asociado" si `info` es null), cuenta sesiones, ordena por contador desc
- [x] 2.5 Implementar `comisionesEnRiesgo(items, materiaNombre): NodoCola[]` — filtra por materia, agrupa por `info.comisionNombre`
- [x] 2.6 Implementar `examenesEnRiesgo(items, materiaNombre, comisionNombre): NodoCola[]` — filtra por materia+comisión, agrupa por `info.examNombre`
- [x] 2.7 Implementar `personasEnRiesgo(items, materiaNombre, comisionNombre, examNombre): SesionEnriquecida[]` — filtra hasta el examen, devuelve las sesiones (personas)
- [x] 2.8 Mantener el archivo ≤ 400 líneas

## 3. Componentes de nivel — `screens/proctoring/`

- [x] 3.1 Crear `ColaBreadcrumb.tsx`: fila propia `flex items-center flex-wrap gap-base`, segmentos clickables ("Materias" raíz › Materia › Comisión › Examen) con chevron; último segmento no clickable; `onNavigate(nivel)` recorta el path. ≤ 400 líneas
- [x] 3.2 Crear `ColaNivelGrid.tsx`: componente genérico `{ titulo, sub, nodos, icono, onSelect }` que renderiza `grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md` de `ColaNivelCard` (Card + nombre + Badge "N en riesgo" en flujo, NADA absolute). Estado vacío incluido. ≤ 400 líneas
- [x] 3.3 Crear `ColaNivelPersonas.tsx`: lista vertical `space-y-sm` de cards de persona (etiqueta + score badge + métricas eventos/discrepancias + botón "Ver detalle"); `onAbrir(sesion)` y `onSeleccionar(sesion)`. ≤ 400 líneas
- [x] 3.4 Crear `ColaPanelDecision.tsx`: panel con 3 botones en palabras llanas ("Sin observaciones" → `sin_hallazgos`, "Aprobar con nota" → `aprobado`, "Enviar a revisión formal" → `flaggeado_para_sumario`), texto aclaratorio (el sistema prioriza, no sanciona), botón "Ver detalle completo". Sin códigos C-NN ni "L2.5" en texto visible. ≤ 400 líneas

## 4. `Revisor.tsx` — orquestador de drill-down

- [x] 4.1 Reescribir `Revisor.tsx`: estado `path: { materia?; comision?; examen? }` y `personaSelId: string | null`; derivar el nivel actual del path
- [x] 4.2 `useEffect` de carga: `api.listarSesionesProctoring()` → `enriquecerYFiltrar(data, UMBRAL_COLA_REVISION)` guardado en estado
- [x] 4.3 Render del header (título + subtítulo de propósito, sin código C-NN ni "L2.5")
- [x] 4.4 Render del `ColaBreadcrumb` en su propia fila, debajo del header
- [x] 4.5 Nivel 1: `ColaNivelGrid` con `materiasEnRiesgo(items)`; onSelect setea `path.materia`
- [x] 4.6 Nivel 2: `ColaNivelGrid` con `comisionesEnRiesgo(items, materia)`; onSelect setea `path.comision`
- [x] 4.7 Nivel 3: `ColaNivelGrid` con `examenesEnRiesgo(items, materia, comision)`; onSelect setea `path.examen`
- [x] 4.8 Nivel 4: `ColaNivelPersonas` con `personasEnRiesgo(...)`; al seleccionar persona muestra `ColaPanelDecision`; "Ver detalle" → `setProctoringSessionId` + navigate `/admin/proctoring-session-detail`
- [x] 4.9 `resolver(decision)`: `setDecisionRevisor(id, decision)` + toast + quita la persona de la vista
- [x] 4.10 Botón "Volver" sube un nivel del path; estado vacío "Cola limpia" cuando no hay sesiones de riesgo
- [x] 4.11 Layout: `space-y-lg`, grids con `gap-md`, cards con `p-lg`, NADA `absolute` sobre texto. Mantener `Revisor.tsx` ≤ 400 líneas
- [x] 4.12 Reusar `Card/Button/Badge/Icon/SectionTitle`, `useToast`. Sin `window.confirm`/`alert`

## 5. Verificación

- [x] 5.1 `npx tsc --noEmit` en `frontend/` = 0 errores
- [x] 5.2 `openspec validate c-48-cola-revision-jerarquica --strict` pasa
- [x] 5.3 Browser (playwright, chromium): ir a `#/revisor`, recorrer drill-down con clicks reales materia → comisión → examen → persona
- [x] 5.4 Screenshot de CADA nivel a 1440x1000 y a 1280x800; confirmar visualmente que NO hay solapamientos en ningún nivel ni tamaño
- [x] 5.5 Si hay solapamiento, arreglar y re-testear; borrar los png temporales al final
