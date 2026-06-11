## ADDED Requirements

### Requirement: ReviewQueueItem como componente de presentación pura
Cada ítem de la cola de revisión SHALL ser un componente `ReviewQueueItem` en `screens/admin/components/ReviewQueueItem.tsx` con props `sesion: SesionRevision`, `selected: boolean`, `onClick: () => void`. Muestra Avatar + nombre + score + examen + fecha + id + incidencias.

#### Scenario: Ítem seleccionado
- **WHEN** `selected === true`
- **THEN** el fondo es `bg-primary-fixed/40 border-primary-container`

#### Scenario: Ítem no seleccionado
- **WHEN** `selected === false`
- **THEN** el fondo es `border-outline-variant/40 hover:bg-surface-container-low`

#### Scenario: Espaciado entre ítems
- **WHEN** hay múltiples ítems en la cola
- **THEN** el contenedor usa `space-y-base` (en vez de `space-y-sm`) para mayor separación entre ítems y menor densidad visual

### Requirement: ReviewDecisionPanel como componente de presentación pura
El panel de resolución de auditoría SHALL ser un componente `ReviewDecisionPanel` en `screens/admin/components/ReviewDecisionPanel.tsx` con props `sesion: SesionRevision`, `onResolver: (decision: SesionRevision['decision'], etiqueta: string) => void`, `onVerDetalle: () => void`.

#### Scenario: Muestra disclaimer L2.5 inamovible
- **WHEN** `ReviewDecisionPanel` está visible
- **THEN** el párrafo "El software no sanciona automáticamente. Tu decisión es obligatoria y queda en el audit log inmutable." está presente e inamovible

#### Scenario: Tres botones de decisión
- **WHEN** el revisor debe tomar una decisión
- **THEN** los tres botones (Descartar / Escalar / Derivar) están presentes con los mismos íconos, variantes y textos de C-anterior; la lógica `alert()` vive en `Revisor.tsx`

#### Scenario: Enlace a detalle forense
- **WHEN** el revisor quiere más contexto
- **THEN** el enlace "Ver detalle forense completo" llama `onVerDetalle()` que navega a `/revisor/detalle`

### Requirement: Revisor.tsx queda como orquestador delgado
Tras la extracción, `Revisor.tsx` SHALL contener solo: estado local (`cola`, `sel`), `cargar()`, `resolver()`, el grid de layout, y los componentes `ReviewQueueItem` (mapeados) + `ReviewDecisionPanel`. La función `groupConsecutiveEvents` permanece en `Revisor.tsx` (local, solo se usa aquí).

#### Scenario: Largo de archivo post-refactor
- **WHEN** se completa la extracción
- **THEN** `Revisor.tsx` tiene ≤80 líneas (bajando de ~195)

### Requirement: Línea de tiempo de anomalías con SectionTitle
El encabezado "Línea de tiempo de anomalías" y "Evidencia y cadena de custodia" en el panel de detalle de Revisor SHALL usar `SectionTitle` (con sub textual) en lugar de `<h3>` con clases manuales.

#### Scenario: Encabezado con sub
- **WHEN** hay anomalías en la sesión seleccionada
- **THEN** `SectionTitle` tiene `sub={`${sel.eventos.length} incidencias`}` u equivalente
