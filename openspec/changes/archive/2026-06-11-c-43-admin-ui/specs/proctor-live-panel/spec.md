## ADDED Requirements

### Requirement: StudentFeedCard como componente de presentación pura
El tile de video de cada estudiante en el mural de monitoreo SHALL ser un componente `StudentFeedCard` en `screens/admin/components/StudentFeedCard.tsx` con las props `sesion: SesionEnVivo` y `umbral: number`. No debe contener hooks ni llamadas a store.

#### Scenario: Renderizado de tile de riesgo alto
- **WHEN** `sesion.score >= umbral`
- **THEN** `StudentFeedCard` muestra borde `border-error shadow-card` y `ScoreChip` con tono de error

#### Scenario: Renderizado de tile normal
- **WHEN** `sesion.score < umbral`
- **THEN** `StudentFeedCard` muestra borde `border-outline-variant/40` y `ScoreChip` con tono success o warning según `score / umbral`

#### Scenario: Badge de escalado
- **WHEN** `sesion.estado === 'escalado'`
- **THEN** `StudentFeedCard` muestra badge "Escalado" en esquina superior izquierda con `bg-error text-on-error`

### Requirement: ProctorControls como componente de presentación pura
El panel lateral de controles (umbral, retos, mensaje correctivo) en Proctor SHALL ser un componente `ProctorControls` en `screens/admin/components/ProctorControls.tsx`. Recibe estado y callbacks como props; no contiene hooks ni store internamente.

#### Scenario: Control de umbral con RangeInput
- **WHEN** el proctor ajusta el umbral
- **THEN** `ProctorControls` usa `RangeInput` (de C-40, `frontend/src/ui/components.tsx`) con `min=30 max=90` y callback `onUmbralChange`; no usa `<input type="range">` raw

#### Scenario: Checkbox de retos con accent-primary
- **WHEN** se muestran los retos activos
- **THEN** los checkboxes usan clase `accent-primary` (no `accent-[#5b5bd6]` hardcoded)

#### Scenario: Envío de mensaje correctivo
- **WHEN** el proctor escribe un mensaje y hace click en "Enviar"
- **THEN** `ProctorControls` llama `onEnviar()` — la lógica del alert vive en `Proctor.tsx` (orquestador), no en el componente

### Requirement: SectionTitle en Proctor
Los encabezados de cards en Proctor SHALL usar `SectionTitle` en lugar de `<h3>` con clases manuales.

#### Scenario: Encabezado "Controles de proctoring"
- **WHEN** el panel de controles está visible
- **THEN** el encabezado usa `SectionTitle` con texto "Controles de proctoring"

#### Scenario: Encabezado "Mensaje correctivo"
- **WHEN** el panel de mensajes está visible
- **THEN** el encabezado usa `SectionTitle` con texto "Mensaje correctivo"

### Requirement: Proctor.tsx queda como orquestador delgado
Tras la extracción, `Proctor.tsx` SHALL contener solo: estado local (`umbral`, `retos`, `destinatario`, `mensaje`, `sesiones`, `scorePropio`, `anomaliasPropias`), el `useEffect` de carga, la función `enviar()`, y el JSX de layout (grid + `SectionTitle` del mural + `StudentFeedCard` mapeados + `ProctorControls`).

#### Scenario: Largo de archivo post-refactor
- **WHEN** se completa la extracción
- **THEN** `Proctor.tsx` tiene ≤80 líneas (bajando de ~113)
