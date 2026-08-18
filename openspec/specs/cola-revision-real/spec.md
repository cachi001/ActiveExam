# cola-revision-real

## Purpose

Define la pantalla de cola de revisión (`Revisor.tsx`) conectada al backend activeexam real (con fallback mock por `USE_REAL_BACKEND`), filtrando exclusivamente las sesiones de alto riesgo (`score >= UMBRAL_COLA_REVISION = 60`), ordenadas por prioridad y enriquecidas con contexto académico. Incluye el panel `ColaPanelDecision` con tres acciones humanas y disclaimer L2.5 inamovible — el sistema nunca sanciona, el score solo prioriza y la decisión es del revisor. Aporta también los tipos (`DecisionRevisor`) y campos (`exam_id`) que el store y el catálogo requieren.

## Requirements

### Requirement: `Revisor.tsx` conectada al backend real con filtro de score

El sistema SHALL reemplazar `api.reviewQueue()` (mock) en `Revisor.tsx` por `api.listarSesionesProctoring()` (dual real/mock, C-46). La cola SHALL mostrar SOLO las sesiones con `score >= UMBRAL_COLA_REVISION` (constante `60` definida al tope del archivo). Las sesiones SHALL ordenarse por score descendente; desempate por `total_discrepancias`. Mientras carga, se muestra spinner. Si no hay sesiones en la cola, se muestra mensaje "¡Cola limpia! No hay sesiones con score ≥ {umbral} pendientes de revisión."

#### Scenario: Carga inicial con backend real
- **WHEN** el componente monta con `USE_REAL_BACKEND=1`
- **THEN** llama `api.listarSesionesProctoring()`, filtra por `score >= 60`, ordena por score desc, muestra la lista resultante

#### Scenario: Carga en modo mock
- **WHEN** el componente monta con `USE_REAL_BACKEND=0`
- **THEN** el mock de `listarSesionesProctoring()` incluye al menos una sesión con score 72 que aparece en la cola

#### Scenario: Cola vacía post-filtro
- **WHEN** ninguna sesión supera el umbral de score
- **THEN** se muestra el estado vacío "¡Cola limpia!" (no se muestra el layout de dos columnas)

#### Scenario: Clic en sesión abre detalle real
- **WHEN** el usuario hace clic en "Ver detalle" en una sesión de la cola
- **THEN** llama `setProctoringSessionId(sesion.id)` y navega a `/admin/proctoring-session-detail` (reutiliza `ProctoringSessionDetail` de C-46)

### Requirement: Panel de resolución humana (`ColaPanelDecision`)

El sistema SHALL proveer un componente local `ColaPanelDecision` en `Revisor.tsx` con tres acciones: "Sin hallazgos", "Aprobar con observación", "Flaggear para sumario". El componente SHALL mostrar un disclaimer L2.5 inamovible: "El sistema nunca sanciona. La decisión es tuya." Al ejecutar una acción, la sesión desaparece de la cola y se muestra un toast de confirmación.

#### Scenario: Resolución registrada en store
- **WHEN** el revisor selecciona una acción de resolución
- **THEN** llama `setDecisionRevisor(sesion.id, decision)` en el store, muestra toast "Decisión registrada: [etiqueta]", elimina la sesión de la vista de cola

#### Scenario: Disclaimer L2.5 inamovible
- **WHEN** el revisor abre el panel de decisión de cualquier sesión
- **THEN** el disclaimer "El sistema nunca sanciona" es visible antes de los botones de acción, no colapsable

#### Scenario: Sin panel si no hay sesión seleccionada
- **WHEN** la cola tiene sesiones pero ninguna está seleccionada
- **THEN** el panel derecho muestra un placeholder invitando a seleccionar una sesión de la cola

### Requirement: Enriquecimiento con contexto académico en la cola

`Revisor.tsx` SHALL enriquecer cada sesión de la cola con `joinExamInfo(sesion.exam_id)` y mostrar nombre de materia y comisión (si disponibles) en el ítem de la cola y en el panel de detalle lateral. Si `exam_id` es null o no matchea el catálogo, se muestra solo el `id` y la `etiqueta`.

#### Scenario: Sesión con exam_id válido muestra contexto académico
- **WHEN** una sesión en la cola tiene `exam_id` que existe en el catálogo local
- **THEN** el ítem de la cola muestra nombre de materia y comisión debajo del score/etiqueta

#### Scenario: Sesión sin exam_id no rompe el renderizado
- **WHEN** una sesión tiene `exam_id` null o undefined
- **THEN** `joinExamInfo` retorna null y el componente renderiza el ítem sin línea de contexto académico

### Requirement: Tipos `DecisionRevisor` y `exam_id` en `SesionProctoringResumen`

El sistema SHALL agregar:
- `export type DecisionRevisor = 'aprobado' | 'flaggeado_para_sumario' | 'sin_hallazgos' | 'pendiente'` en `types.ts`
- Campo `exam_id?: string | null` a la interfaz `SesionProctoringResumen` en `types.ts`
- Campos `decisionesRevisor: Record<string, DecisionRevisor>` y acción `setDecisionRevisor(id: string, decision: DecisionRevisor): void` al store Zustand en `store.ts`

#### Scenario: `DecisionRevisor` importable desde types.ts
- **WHEN** un componente importa `DecisionRevisor` desde `'../lib/types'`
- **THEN** el tipo es resolvible en TypeScript sin errores de compilación

#### Scenario: `exam_id` en el mock de `listarSesionesProctoring`
- **WHEN** el mock de `listarSesionesProctoring()` retorna la sesión de score 72
- **THEN** dicha sesión incluye `exam_id: 'EXAM-AMAT-2025-01'` y `joinExamInfo` la resuelve correctamente

### Requirement: Subtítulo diferenciador en `Revisor.tsx`

`Revisor.tsx` SHALL actualizar su header con subtítulo: "Sesiones de alto riesgo (score ≥ 60) priorizadas para revisión. El sistema nunca sanciona." El subtítulo SHALL diferenciar claramente el propósito de esta pantalla vs. "Sesiones grabadas" (historial) y "Supervisión en vivo" (activas ahora).

#### Scenario: Subtítulo visible en la pantalla
- **WHEN** el revisor navega a `/revisor`
- **THEN** el subtítulo explica el umbral de score y menciona L2.5
