## Context

Las tres pantallas del área de proctoring ya existen y funcionan post-C-46:

- `Revisor.tsx` — cola mock (`api.reviewQueue()` / `COLA_REVISION`). Tiene `ReviewQueueItem` + `ReviewDecisionPanel` extraídos (C-43).
- `ProctoringRevisor.tsx` — historial real (`api.listarSesionesProctoring()`). Usa `SesionCard`, `ResumenSesiones`, `ListaEstados`.
- `Proctor.tsx` — polling real (`api.listarSesionesProctoring()` cada 4s). Usa `SesionVivoCard`, `ResumenVivo`, `IndicadorVivo`.
- `ProctoringSessionDetail.tsx` — detalle real (C-46). Muestra eventos, screenshots, biometría. Ya es la pantalla destino correcta.

El catálogo académico local existe en `api.ts` como arrays `EXAMENES`, `COMISIONES`, `MATERIAS`. `SesionProctoringResumen.exam_id` está tipado como `string` en el backend slim (enviado opcionalmente en `crearSesionProctoring`). El tipo en `types.ts` no tiene `exam_id` todavía — hay que agregarlo como campo opcional.

Restricciones:
- **Dual-mode obligatorio**: `USE_REAL_BACKEND=0` → mock completo; la cola en mock muestra sesiones de ejemplo con score ≥ 60.
- **No buildear, no commitear** sin pedido explícito.
- **L2.5**: el score es acumulador de priorización, nunca veredicto. La resolución humana es obligatoria.
- **Ley 25.326**: no listar `screenshot_base64` en la lista de cola; solo en el detalle.
- **Sin breaking changes**: props nuevas siempre opcionales; el mock sigue funcionando.
- **`joinExamInfo` sin llamadas HTTP**: función pura que trabaja sobre los arrays locales importados directamente de `api.ts` (o reexportados).

## Goals / Non-Goals

**Goals:**
- `Revisor.tsx` conectada al backend real filtrada por `score >= UMBRAL_COLA_REVISION` (60).
- Join `exam_id` → catálogo local para enriquecer las tres pantallas con contexto académico.
- Acción de resolución humana en la Cola: tipo `DecisionRevisor` + estado local persistido en store.
- `ProctoringRevisor` con subtítulo de propósito claro.
- `Proctor` con diferenciación visual por estado (`modo === 'examen'` vs diagnóstico).
- `SesionCard` + `SesionVivoCard` con prop opcional `examInfo`.
- `helpers.ts` con `joinExamInfo` pura.

**Non-Goals:**
- Endpoint backend para guardar decisiones del revisor (el backend slim no tiene tabla de decisiones).
- Paginación en la cola (MVP — el backend devuelve todas).
- Notificaciones en tiempo real (WebSocket/SSE — no está en el backend slim).
- Filtro por fecha/materia en la cola (roadmap futuro).
- Identidad del alumno por sesión (el backend slim no tiene auth; la demo no vincula alumno real a sesión).

## Decisions

### D1: `Revisor.tsx` — nueva fuente de datos: `listarSesionesProctoring()` + filtro score

Reemplazar `api.reviewQueue()` por `api.listarSesionesProctoring()`. Filtrar el resultado con `sesiones.filter(s => s.score >= UMBRAL_COLA_REVISION)`. Ordenar por score desc (mayor riesgo primero). El mock de `listarSesionesProctoring()` ya existe en C-46 y retorna sesiones con scores variados; el filtro de umbral actúa sobre ese mock también.

Alternativa descartada: nuevo método `api.listarSesionesAltoRiesgo(umbral)` — overhead innecesario; el filtro en el cliente es trivial y el backend slim ya no tiene lógica de filtro por score. El patrón es consistente con `Proctor.tsx` que ya filtra/ordena en cliente.

### D2: `UMBRAL_COLA_REVISION` como constante local en `Revisor.tsx`

`const UMBRAL_COLA_REVISION = 60;` definida al tope del archivo. No se exporta, no va al store. El revisor puede conceptualmente cambiar el umbral en el futuro (C-futura: selector de umbral en la cola), pero para esta demo un valor fijo es correcto y no complica el estado. No va a `INSTITUTION` porque es lógica de negocio de proctoring, no de configuración institucional.

Alternativa descartada: constante en `helpers.ts` → duplica responsabilidades; la pantalla es la única que la necesita.

### D3: `joinExamInfo` como función pura en `helpers.ts`

```typescript
export interface ExamInfo {
  examNombre: string;
  materiaNombre: string;
  comisionNombre: string;
  docente: string;
}

export function joinExamInfo(examId: string | null | undefined): ExamInfo | null
```

Importa los arrays `EXAMENES`, `COMISIONES`, `MATERIAS` directamente desde `'../../lib/api'` (ya son exports del módulo). Busca: `examen = EXAMENES.find(e => e.id === examId)` → `comision = COMISIONES.find(c => c.id === examen.comision_id)` → `materia = MATERIAS.find(m => m.id === comision.materia_id)`. Retorna `null` si cualquier lookup falla (sesión de harness sin `exam_id` real).

Alternativa descartada: llamar `api.getExam(examId)` (async) desde el componente — complica el renderizado con más estados de carga por sesión; la función pura síncrona es trivial y suficiente para la demo.

### D4: `SesionProctoringResumen` → agregar `exam_id?: string | null`

El campo `exam_id` se envía en `crearSesionProctoring` al backend slim, que lo persiste en `proctoring_session.exam_id`. El tipo en `types.ts` no lo tiene todavía. Se agrega como `exam_id?: string | null`. Es aditivo — no rompe código existente.

El `SesionProctoringDetalle` hereda el campo via `extends SesionProctoringResumen`.

### D5: Decisión del revisor — `DecisionRevisor` en `types.ts` + registro en store

```typescript
export type DecisionRevisor = 'aprobado' | 'flaggeado_para_sumario' | 'sin_hallazgos' | 'pendiente';
```

El store Zustand recibe un nuevo campo `decisionesRevisor: Record<string, DecisionRevisor>` (mapa `sessionId → decision`) y su setter `setDecisionRevisor(id: string, decision: DecisionRevisor): void`. Valor inicial: `{}`.

`Revisor.tsx` lee `decisionesRevisor` del store para mostrar el estado de cada sesión en la cola (badge de estado). Al resolver, llama `setDecisionRevisor(sesion.id, decision)` y filtra la sesión de la vista local (igual que hoy con `COLA_REVISION`). Un toast confirma la acción con el texto: `"Decisión registrada: [etiqueta]. El score prioriza; el revisor decide."`.

Alternativa descartada: localStorage para persistir decisiones → innecesario para la demo; el store es suficiente y sigue el patrón de C-46 (`proctoringSessionId`).

### D6: `Proctor.tsx` — diferenciación por `modo`

Las sesiones de proctoring tienen campo `modo: string`. El harness diagnóstico crea sesiones con `modo: 'diagnostico'`; el examen real usa `modo: 'examen'`. La diferenciación es visual:

- Sesiones `modo === 'examen'` → sección "Activas: examen en curso" con badge verde pulsante.
- Sesiones `modo === 'diagnostico'` → sección "Diagnóstico" con badge gris.
- Sesiones con `modo` desconocido → van a "Otras".

La separación es con `useMemo` que particiona la lista: `const { examen, diagnostico, otras } = useMemo(() => { ... }, [sesiones])`. Se renderizan tres secciones con `SectionTitle` y `SesionVivoCard` correspondientes. Cada `SesionVivoCard` recibe `examInfo` opcional del `joinExamInfo`.

Alternativa descartada: heurística de "reciente actividad" por `creada_en` — más compleja, falible. El campo `modo` es el discriminador correcto.

### D7: Panel de resolución en `Revisor.tsx` — reusar `ReviewDecisionPanel` o reemplazar

`ReviewDecisionPanel` (C-43) acepta `sesion: SesionRevision` y llama `onResolver(decision, etiqueta)`. La nueva cola trabaja con `SesionProctoringResumen`, no con `SesionRevision`. Dos opciones:

**Opción elegida**: crear inline en `Revisor.tsx` un componente local `<ColaPanelDecision>` que acepta `sesion: SesionProctoringResumen` y `onResolver: (d: DecisionRevisor) => void`. Es pequeño (3 botones + descripción L2.5). No justifica extraerlo ya que `ReviewDecisionPanel` seguirá existiendo para el flujo mock de revisión académica.

Alternativa descartada: modificar `ReviewDecisionPanel` para aceptar ambos tipos — polimorfismo innecesario que contamina el componente existente y crea acoplamiento entre dos flujos distintos.

### D8: `ProctoringRevisor.tsx` — enriquecimiento con `joinExamInfo`

Al renderizar cada `SesionCard`, calcular `joinExamInfo(sesion.exam_id)` y pasarlo como prop `examInfo` opcional. El cálculo es síncrono (función pura), no requiere estado adicional.

`SesionCard` recibe un nuevo prop `examInfo?: ExamInfo | null` y lo muestra en una línea extra debajo del `id/etiqueta`: `{examInfo?.materiaNombre} · {examInfo?.comisionNombre}`. Si `examInfo` es null (sesión de harness sin exam_id), no muestra nada extra.

### D9: Mock de cola en `Revisor.tsx` — `USE_REAL_BACKEND=0`

Cuando `USE_REAL_BACKEND=0`, `listarSesionesProctoring()` retorna el mock de C-46 (dos sesiones con score 38 y 12). Con `UMBRAL_COLA_REVISION = 60`, la cola quedaría vacía — lo que no es útil para la demo. Por tanto, el mock en `api.ts` debe incluir al menos una sesión con score ≥ 60.

Actualizar el mock de `listarSesionesProctoring()` para incluir una sesión de score 72 (`modo: 'examen'`, `exam_id: 'EXAM-AMAT-2025-01'` — uno de los IDs del catálogo real) y otra de score 38. Así la cola muestra una sesión en modo mock.

## Risks / Trade-offs

- **[Riesgo] `SesionProctoringResumen.exam_id` puede no venir del backend slim actual** → Mitigation: campo opcional (`exam_id?: string | null`); si no viene, `joinExamInfo` retorna null y los componentes muestran solo el id/etiqueta existente. El backend slim C-45 ya persiste `exam_id` desde el `POST /sessions` — solo necesita que `crearSesionProctoring` lo envíe, lo que ya hace.
- **[Riesgo] `EXAMENES` / `COMISIONES` / `MATERIAS` son arrays locales que podrían cambiar** → Mitigation: `joinExamInfo` es una función pura sobre imports estáticos — si los arrays cambian, la función sigue siendo correcta. No hay estado compartido mutable.
- **[Trade-off] Decisiones del revisor en store (no persistidas en backend)** → A cambio, no se introduce ningún endpoint nuevo en el backend slim (que es un módulo de demo); las decisiones sobreviven mientras la sesión esté activa. Si el usuario recarga la página, las decisiones se pierden — aceptable en demo.
- **[Riesgo] `Revisor.tsx` cambia su fuente de datos** → El mock legacy `COLA_REVISION` / `api.reviewQueue()` deja de usarse en `Revisor.tsx`. La función `reviewQueue` y `resolveReview` de `api.ts` se vuelven dead code si `Revisor` es la única que las llamaba. No se eliminan ahora (son parte del contrato de `api.ts`), solo se dejan de usar.

## Migration Plan

1. Agregar `exam_id?: string | null` a `SesionProctoringResumen` en `types.ts` — aditivo.
2. Agregar `DecisionRevisor` a `types.ts` — nuevo tipo.
3. Agregar `decisionesRevisor` + `setDecisionRevisor` al store `store.ts` — campo nuevo.
4. Actualizar mock de `listarSesionesProctoring()` en `api.ts` — agregar sesión con score 72 y exam_id.
5. Agregar `joinExamInfo` + `ExamInfo` a `helpers.ts` — nuevo export, sin romper existentes.
6. Extender `SesionCard` con prop `examInfo?` — prop opcional, sin romper callers existentes.
7. Extender `SesionVivoCard` con prop `examInfo?` — idem.
8. Modificar `Revisor.tsx` — nueva fuente de datos + cola real + panel de decisión.
9. Modificar `ProctoringRevisor.tsx` — subtítulo + join de catálogo.
10. Modificar `Proctor.tsx` — partición por modo + join de catálogo.

Rollback: los pasos 1–7 son aditivos y no rompen nada. Los pasos 8–10 son los únicos con cambio de comportamiento. Revertir es restaurar las fuentes de datos anteriores en las tres pantallas.

## Open Questions

- ¿El backend slim actual ya retorna `exam_id` en el GET `/sessions`? Asumo que sí (la columna está en el modelo C-45 y se persiste desde el POST). Verificar al aplicar.
- ¿El campo `modo` del backend slim es exactamente `'examen'` o puede ser otro string? El harness usa `'diagnostico'` (string en el POST), el examen real debería usar `'examen'`. Confirmar al leer `main_slim.py` antes de aplicar.
- ¿La pantalla `Revisor.tsx` debe conservar el panel de "cadena de custodia" (mock con `hash_cliente` / `rehash_backend`)? En la nueva cola real no hay cadena de custodia simulada — el detalle real está en `ProctoringSessionDetail`. Se propone eliminar el panel de custodia mock de `Revisor.tsx` y reemplazarlo con un link "Ver detalle completo" que navega a `ProctoringSessionDetail`. Si el usuario quiere conservarlo para la demo visual, mencionarlo en el apply.
