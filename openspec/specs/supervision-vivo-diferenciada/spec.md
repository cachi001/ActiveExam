## MODIFIED Requirements

> Modifica `proctor-live-panel` (C-43/C-46) — agrega partición visual por modo de sesión y enriquecimiento con contexto académico.

### Requirement: Partición visual por modo en `Proctor.tsx`

`Proctor.tsx` SHALL particionar las sesiones en tres grupos con `useMemo`: `examen` (modo === 'examen'), `diagnostico` (modo === 'diagnostico'), `otras` (resto). SHALL renderizar secciones distintas con `SectionTitle` para cada grupo no vacío. La sección "examen" SHALL mostrarse primero, con un badge visual diferenciador. Si un grupo está vacío, su sección no se renderiza. El estado vacío global (`ListaVaciaVivo`) se muestra solo si `sesiones.length === 0`.

#### Scenario: Sesiones de examen aparecen primero
- **WHEN** el panel carga y tiene sesiones con `modo === 'examen'` y `modo === 'diagnostico'`
- **THEN** la sección "Exámenes en curso" se renderiza antes de "Diagnóstico / harness"

#### Scenario: Solo sesiones de diagnóstico
- **WHEN** todas las sesiones activas tienen `modo === 'diagnostico'`
- **THEN** se renderiza solo la sección "Diagnóstico / harness"; la sección "Exámenes en curso" no aparece

#### Scenario: Sin sesiones activas
- **WHEN** `sesiones.length === 0` tras la carga inicial
- **THEN** se renderiza `ListaVaciaVivo` (comportamiento actual intacto)

#### Scenario: Polling continúa con partición activa
- **WHEN** llega un nuevo ciclo del `setInterval` de polling (cada 4s)
- **THEN** las sesiones se vuelven a particionar y las secciones se actualizan correctamente

### Requirement: Subtítulo diferenciador en `Proctor.tsx`

`Proctor.tsx` SHALL actualizar su subtítulo de header a: "Monitoreo en tiempo real. Exámenes en curso se muestran primero. El score prioriza para revisión humana; nunca sanciona." El subtítulo SHALL diferenciar claramente el propósito de esta pantalla vs. "Sesiones grabadas" (historial) y "Cola de revisión" (alto riesgo pendiente de decisión).

#### Scenario: Subtítulo visible al cargar el panel
- **WHEN** el operador navega a `/proctor`
- **THEN** el subtítulo actualizado es visible en el header de la pantalla

## ADDED Requirements

### Requirement: Join de catálogo en `Proctor.tsx` para sesiones de examen

`Proctor.tsx` SHALL calcular `joinExamInfo(sesion.exam_id)` para cada sesión con `modo === 'examen'` y pasar el resultado como prop `examInfo` a `SesionVivoCard`. Las sesiones de diagnóstico NO necesitan join (no tienen exam_id relevante).

#### Scenario: Sesión de examen con exam_id muestra contexto en `SesionVivoCard`
- **WHEN** una sesión activa tiene `modo === 'examen'` y `exam_id` válido en el catálogo
- **THEN** `SesionVivoCard` muestra nombre de materia y docente en la card del panel en vivo

#### Scenario: Sesión de diagnóstico sin join
- **WHEN** una sesión activa tiene `modo === 'diagnostico'`
- **THEN** `SesionVivoCard` se renderiza sin `examInfo` (comportamiento existente intacto)
