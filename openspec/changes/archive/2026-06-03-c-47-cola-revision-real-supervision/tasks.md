## 1. Tipos y store — base para el change

- [x] 1.1 Agregar `exam_id?: string | null` a `SesionProctoringResumen` en `frontend/src/lib/types.ts` — campo aditivo, no rompe código existente
- [x] 1.2 Agregar `export type DecisionRevisor = 'aprobado' | 'flaggeado_para_sumario' | 'sin_hallazgos' | 'pendiente'` en `frontend/src/lib/types.ts`
- [x] 1.3 Exportar `DecisionRevisor` desde `frontend/src/lib/types.ts`
- [x] 1.4 Agregar campo `decisionesRevisor: Record<string, DecisionRevisor>` al store Zustand en `frontend/src/lib/store.ts` con valor inicial `{}`
- [x] 1.5 Agregar acción `setDecisionRevisor(id: string, decision: DecisionRevisor): void` al store
- [x] 1.6 Exportar el tipo del slice correspondiente si corresponde al patrón del archivo

## 2. Mock `listarSesionesProctoring()` — actualizar para cola funcional

- [x] 2.1 En `frontend/src/lib/api.ts`, agregar al array mock de `listarSesionesProctoring()` una sesión con `score: 72`, `modo: 'examen'`, `exam_id: 'EXAM-AMAT-2025-01'` (ID existente en EXAMENES), `total_eventos: 5`, `total_discrepancias: 2`, `etiqueta: 'Final AMAT — Comisión 1A'`
- [x] 2.2 Verificar que el mock existente de score 38 se mantiene intacto (la cola filtra por umbral 60, debe mostrar solo la sesión de score 72 en modo mock)
- [x] 2.3 Verificar que `getSesionProctoring` mock también puede retornar detalle para el `id` de la sesión de score 72 (o que el mock genérico es suficiente)

## 3. `joinExamInfo` en `helpers.ts`

- [x] 3.1 Agregar interfaz `ExamInfo { examNombre: string; materiaNombre: string; comisionNombre: string; docente: string }` en `frontend/src/screens/proctoring/helpers.ts`
- [x] 3.2 Importar `EXAMENES`, `COMISIONES`, `MATERIAS` desde `'../../lib/api'` en `helpers.ts`
- [x] 3.3 Implementar `export function joinExamInfo(examId: string | null | undefined): ExamInfo | null` con la cadena de lookup: `EXAMENES.find → COMISIONES.find → MATERIAS.find`
- [x] 3.4 Manejar todos los casos de null/undefined: si `examId` es falsy retornar null inmediatamente; si cualquier lookup falla retornar null
- [x] 3.5 Envolver en try/catch y retornar null en caso de cualquier excepción inesperada (sin propagar)
- [x] 3.6 Exportar `ExamInfo` y `joinExamInfo` desde `helpers.ts`
- [x] 3.7 Verificar que la función no llama a `api`, no usa hooks, no accede al store (función pura)

## 4. `SesionCard` — prop `examInfo` opcional

- [x] 4.1 Importar `ExamInfo` desde `'./helpers'` en `frontend/src/screens/proctoring/SesionCard.tsx`
- [x] 4.2 Agregar prop `examInfo?: ExamInfo | null` a la interfaz de props del componente
- [x] 4.3 Si `examInfo` no es null, renderizar una línea adicional debajo del título/etiqueta: `{examInfo.materiaNombre} · {examInfo.comisionNombre}` en `text-label-sm text-on-surface-variant`
- [x] 4.4 Si `examInfo` es null o undefined, no renderizar la línea adicional (comportamiento actual intacto)
- [x] 4.5 Verificar que todos los callers existentes de `SesionCard` siguen compilando (prop opcional, sin cambios requeridos en callers que no la pasan)

## 5. `SesionVivoCard` — prop `examInfo` opcional

- [x] 5.1 Importar `ExamInfo` desde `'./helpers'` en `frontend/src/screens/proctoring/SesionVivoCard.tsx`
- [x] 5.2 Agregar prop `examInfo?: ExamInfo | null` a la interfaz de props del componente
- [x] 5.3 Si `examInfo` no es null, renderizar nombre de materia y docente en una línea compacta dentro de la card
- [x] 5.4 Si `examInfo` es null o undefined, comportamiento actual intacto
- [x] 5.5 Verificar que el caller existente en `Proctor.tsx` sigue compilando sin cambios

## 6. `Revisor.tsx` — cola real conectada al backend

- [x] 6.1 Agregar `const UMBRAL_COLA_REVISION = 60;` al tope de `Revisor.tsx` (por debajo de los imports)
- [x] 6.2 Reemplazar import de `SesionRevision` y `api.reviewQueue()` / `api.resolveReview()` por `api.listarSesionesProctoring()` y tipos de proctoring
- [x] 6.3 Importar `SesionProctoringResumen`, `DecisionRevisor` desde `'../lib/types'`
- [x] 6.4 Importar `joinExamInfo`, `ExamInfo` desde `'./proctoring/helpers'`
- [x] 6.5 Importar `useApp` para leer `setProctoringSessionId` y `setDecisionRevisor` del store
- [x] 6.6 Reemplazar el estado `cola: SesionRevision[]` por `cola: SesionProctoringResumen[]`
- [x] 6.7 En el `useEffect` de carga: llamar `api.listarSesionesProctoring()`, filtrar `s.score >= UMBRAL_COLA_REVISION`, ordenar por `score desc` (desempate por `total_discrepancias`)
- [x] 6.8 Para cada sesión en la cola, calcular `joinExamInfo(sesion.exam_id)` y guardarlo en un Map local (o calcularlo inline al renderizar — ver D3)
- [x] 6.9 Implementar componente local `ColaPanelDecision({ sesion, examInfo, onResolver })` con 3 botones de acción y disclaimer L2.5 inamovible:
  - [x] 6.9.1 Botón "Sin hallazgos" → llama `onResolver('sin_hallazgos')`
  - [x] 6.9.2 Botón "Aprobar con observación" → llama `onResolver('aprobado')`
  - [x] 6.9.3 Botón "Flaggear para sumario" (variante danger) → llama `onResolver('flaggeado_para_sumario')`
  - [x] 6.9.4 Disclaimer L2.5: texto "El sistema nunca sanciona. La decisión es tuya."
- [x] 6.10 Implementar función `resolver(decision: DecisionRevisor)`: llama `setDecisionRevisor(sel.id, decision)`, muestra toast, filtra la sesión de `cola` (igual que hoy)
- [x] 6.11 Al hacer click "Ver detalle" en una sesión: llamar `setProctoringSessionId(sesion.id)` y `navigate('/admin/proctoring-session-detail')` — reusar `ProctoringSessionDetail` existente
- [x] 6.12 Eliminar el panel de "cadena de custodia" mock (hash_cliente / rehash_backend) — reemplazar con link "Ver detalle completo →" que navega a `/admin/proctoring-session-detail`
- [x] 6.13 Usar `ReviewQueueItem` de C-43 para el ítem en la cola lateral si su interfaz de props es compatible; de lo contrario, renderizar un item simple con `score`, `total_eventos`, `examInfo?.materiaNombre`
- [x] 6.14 Actualizar header: subtítulo "Sesiones de alto riesgo (score ≥ {UMBRAL_COLA_REVISION}) priorizadas para revisión. El sistema nunca sanciona."
- [x] 6.15 Estado vacío: mensaje "¡Cola limpia! No hay sesiones con score ≥ {UMBRAL_COLA_REVISION} pendientes de revisión."

## 7. `ProctoringRevisor.tsx` — subtítulo y join de catálogo

- [x] 7.1 Importar `joinExamInfo` desde `'./proctoring/helpers'` en `ProctoringRevisor.tsx`
- [x] 7.2 Actualizar el párrafo de subtítulo del header a: "Historial completo de sesiones de proctoring — todas las grabadas, sin filtro. Para revisar solo las de alto riesgo, usá la Cola de revisión."
- [x] 7.3 Al renderizar cada `SesionCard`, calcular `joinExamInfo(s.exam_id)` y pasarlo como prop `examInfo`
- [x] 7.4 Verificar que `SesionProctoringResumen` ya incluye `exam_id` (paso 1.1) antes de usarlo

## 8. `Proctor.tsx` — diferenciación visual por modo

- [x] 8.1 Importar `joinExamInfo` desde `'./proctoring/helpers'` en `Proctor.tsx`
- [x] 8.2 Agregar `useMemo` que particiona `sesiones` en tres grupos: `examen` (modo === 'examen'), `diagnostico` (modo === 'diagnostico'), `otras` (resto)
- [x] 8.3 Reemplazar la sección única de lista por tres secciones condicionales:
  - [x] 8.3.1 Sección "Exámenes en curso": si `examen.length > 0`, `SectionTitle` con sub `"{examen.length} examen(es) activo(s)"` + badge verde pulsante + lista de `SesionVivoCard` con `examInfo`
  - [x] 8.3.2 Sección "Diagnóstico / harness": si `diagnostico.length > 0`, `SectionTitle` con sub + lista de `SesionVivoCard`
  - [x] 8.3.3 Sección "Otras": si `otras.length > 0`, lista de `SesionVivoCard` sin diferenciación especial
- [x] 8.4 Actualizar el subtítulo del header: "Monitoreo en tiempo real. Exámenes en curso se muestran primero. El score prioriza para revisión humana; nunca sanciona."
- [x] 8.5 Al renderizar `SesionVivoCard` de la sección `examen`, pasar `examInfo={joinExamInfo(s.exam_id)}`
- [x] 8.6 Verificar que el polling y el botón de actualización manual siguen funcionando igual

## 9. Verificación final

- [x] 9.1 Verificar que `openspec validate --strict` pasa sin errores para el change c-47
- [x] 9.2 Verificar que con `USE_REAL_BACKEND=0` la cola de `Revisor.tsx` muestra la sesión de score 72 del mock actualizado
- [x] 9.3 Verificar que `ProctoringRevisor.tsx` muestra subtítulo actualizado y `examInfo` cuando `exam_id` es `'EXAM-AMAT-2025-01'`
- [x] 9.4 Verificar que `Proctor.tsx` muestra dos secciones diferenciadas cuando hay sesiones de ambos modos en el mock
- [x] 9.5 Verificar que `SesionCard` y `SesionVivoCard` compilan correctamente con y sin prop `examInfo`
- [x] 9.6 Verificar que `joinExamInfo('EXAM-AMAT-2025-01')` retorna objeto no-null con los datos del catálogo (examen/comisión/materia del array EXAMENES)
- [x] 9.7 Verificar que `joinExamInfo(undefined)` y `joinExamInfo(null)` retornan null sin lanzar excepción
- [x] 9.8 Verificar que el panel `ColaPanelDecision` muestra el disclaimer L2.5 y los 3 botones de acción
- [x] 9.9 Verificar que `Revisor.tsx` navega a `/admin/proctoring-session-detail` al hacer click en "Ver detalle" (reusar `ProctoringSessionDetail`)
- [x] 9.10 Verificar que `tsc --noEmit` pasa sin errores en `frontend/`
