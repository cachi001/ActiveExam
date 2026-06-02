## ADDED Requirements

### Requirement: QuickAccessCard component
El sistema SHALL proveer un componente `QuickAccessCard` que renderice un acceso rápido de navegación con ícono, título, descripción y flecha. Recibe `icon`, `title`, `description`, `onClick` como props. No gestiona estado propio.

#### Scenario: Render acceso rápido
- **WHEN** se monta `QuickAccessCard` con `icon="menu_book"`, `title="Mis materias"`, `description="Explorar y inscribirse"`, `onClick={fn}`
- **THEN** se muestra un botón con el ícono Material, el título en `text-label-md font-semibold`, la descripción en `text-label-sm text-on-surface-variant` y una flecha `arrow_forward` a la derecha

#### Scenario: Click dispara callback
- **WHEN** el usuario clickea el componente
- **THEN** se invoca `onClick` sin argumentos

---

### Requirement: ExamenProximoCard component
El sistema SHALL proveer un componente `ExamenProximoCard` que renderice una inscripción próxima (estado `inscripto` o `habilitado`) con ícono de evento, nombre del examen, nombre de la materia, fecha formateada y badge de estado. Props: `inscripcion: Inscripcion`.

#### Scenario: Render card de examen próximo
- **WHEN** se monta `ExamenProximoCard` con una `Inscripcion` de estado `habilitado`
- **THEN** se muestra el nombre del examen, la materia, la fecha en formato `es-AR` y el badge con tone `success`

#### Scenario: Badge refleja estado de la inscripción
- **WHEN** la inscripción tiene estado `inscripto`
- **THEN** el badge muestra "Inscripto" con tone `primary`

---

### Requirement: MateriaCard component
El sistema SHALL proveer un componente `MateriaCard` que renderice una materia como acordeón expandible. Props: `materia: Materia`, `activa: boolean`, `cargandoComisiones: boolean`, `comisiones: Comision[]`, `comisionSeleccionada: Comision | null`, `cargandoExamenes: boolean`, `examenes: Examen[]`, `inscripciones: Inscripcion[]`, `inscribiendoId: string | null`, `onSelect: () => void`, `onSelectComision: (c: Comision) => void`, `onInscribir: (examenId: string) => void`. No llama a `api` ni usa el store.

#### Scenario: Materia colapsada
- **WHEN** `activa === false`
- **THEN** se muestra solo el encabezado de la materia (nombre, código, descripción) con ícono `expand_more`

#### Scenario: Materia expandida muestra comisiones
- **WHEN** `activa === true` y `cargandoComisiones === false` y `comisiones.length > 0`
- **THEN** se renderizan `ComisionRow` por cada comisión con indent `ml-lg`

#### Scenario: Materia expandida sin comisiones
- **WHEN** `activa === true` y `cargandoComisiones === false` y `comisiones.length === 0`
- **THEN** se muestra el texto "No hay comisiones disponibles."

#### Scenario: Cargando comisiones
- **WHEN** `activa === true` y `cargandoComisiones === true`
- **THEN** se muestra spinner `progress_activity` con texto "Cargando comisiones…"

---

### Requirement: ComisionRow component
El sistema SHALL proveer un componente `ComisionRow` que renderice una comisión como acordeón anidado con el nombre, docente, horario y lista de `ExamenCard` cuando está activa. Props: `comision: Comision`, `activa: boolean`, `cargandoExamenes: boolean`, `examenes: Examen[]`, `inscripciones: Inscripcion[]`, `inscribiendoId: string | null`, `onSelect: () => void`, `onInscribir: (examenId: string) => void`.

#### Scenario: Comisión colapsada
- **WHEN** `activa === false`
- **THEN** se muestra solo el nombre, docente y horario con ícono `expand_more`

#### Scenario: Comisión expandida muestra exámenes
- **WHEN** `activa === true` y `cargandoExamenes === false` y `examenes.length > 0`
- **THEN** se renderizan `ExamenCard` por cada examen con indent `ml-lg`

#### Scenario: Sin exámenes en la comisión
- **WHEN** `activa === true` y `cargandoExamenes === false` y `examenes.length === 0`
- **THEN** se muestra "No hay exámenes en esta comisión."

---

### Requirement: ExamenCard component
El sistema SHALL proveer un componente `ExamenCard` que renderice un examen con nombre, fecha, duración, badge de estado y botón "Inscribirme" si corresponde. Props: `examen: Examen`, `inscripto: boolean`, `inscribiendo: boolean`, `onInscribir: () => void`.

#### Scenario: Examen ya inscripto
- **WHEN** `inscripto === true`
- **THEN** se muestra badge "Inscripto" con tone `success` y no se muestra el botón "Inscribirme"

#### Scenario: Examen programado no inscripto
- **WHEN** `examen.estado === "programado"` y `inscripto === false`
- **THEN** se muestra el botón "Inscribirme" habilitado; al clickear invoca `onInscribir`

#### Scenario: Examen no programado
- **WHEN** `examen.estado !== "programado"`
- **THEN** no se muestra el botón de inscripción; solo el badge del estado del examen

#### Scenario: Inscribiendo en progreso
- **WHEN** `inscribiendo === true`
- **THEN** el botón muestra spinner + "Inscribiendo…" y está deshabilitado

---

### Requirement: InscripcionCard component
El sistema SHALL proveer un componente `InscripcionCard` que renderice una inscripción con ícono de estado, nombre del examen, materia, fecha, badge de estado y la acción correspondiente según el gate en capas (C-26). Props: `inscripcion: Inscripcion`, `gate: GatePorExamen | undefined`, `verificando: boolean`, `onRendir: () => void`, `onCompletarAcuse: () => void`, `onIrAPerfil: () => void`. No gestiona el gate internamente.

#### Scenario: Estado habilitado — gate completo
- **WHEN** `inscripcion.estado === "habilitado"` y `gate.puede === true`
- **THEN** se muestra el botón "Rendir" con ícono `play_arrow`

#### Scenario: Estado habilitado — falta acuse (C-26)
- **WHEN** `inscripcion.estado === "habilitado"` y `gate.puede === false` y `gate.codigo === "acuse_examen_faltante"`
- **THEN** se muestra el texto "Falta el acuse de consentimiento" y el botón "Completar acuse del examen"

#### Scenario: Estado habilitado — perfil incompleto
- **WHEN** `inscripcion.estado === "habilitado"` y `gate.puede === false` y `gate.codigo !== "acuse_examen_faltante"`
- **THEN** se muestra el texto descriptivo según el código y el botón "Completar perfil" o "Renovar biometría"

#### Scenario: Estado rendido
- **WHEN** `inscripcion.estado === "rendido"`
- **THEN** se muestra el texto "Examen completado. El resultado está sujeto a revisión académica." sin botón de acción

#### Scenario: Verificando gate en progreso
- **WHEN** `verificando === true`
- **THEN** el botón de rendir muestra spinner + "Verificando…" y está deshabilitado
