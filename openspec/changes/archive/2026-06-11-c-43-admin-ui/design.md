## Context

El área admin/staff tiene 7 pantallas en `frontend/src/screens/`. C-40 limpió la base (Button con sizes, RangeInput, FormField, sin jerga dev). C-41/C-42 establecieron el patrón de colocalización: componentes de presentación pura en `screens/<rol>/components/`. Las pantallas admin nunca pasaron por ese mismo tratamiento.

Estado actual por pantalla:

| Pantalla | Líneas | Problema principal |
|---|---|---|
| AdminDashboard.tsx | ~71 | Ya relativamente limpia; "Acciones rápidas" usa `<h3>` suelto; botones sin size explícito (hereda `md` por default — OK); tabla de exámenes bien. |
| ExamList.tsx | ~74 | `<button>` raw "Configurar" con clases manuales en vez de `Button size="sm"`; input de búsqueda con clases custom bien pero sin `FormField`. |
| Reports.tsx | ~76 | Barra de progreso de severidad usa `<div>` inline en vez de `ProgressBar`; leyenda semanal OK; insight card OK. |
| Revisor.tsx | ~195 | La más densa: cola en col-1 + detalle+decisión en col-2 — funciona pero sin componentes extraídos; panel de decisión (~30 líneas) inline; `groupConsecutiveEvents` es lógica local reutilizable. |
| SessionDetail.tsx | ~141 | Bien estructurada — `CadenaPaso` ya extraída; "Eventos discretos" usa `<h3>` en vez de `SectionTitle`. |
| Proctor.tsx | ~113 | Monolítica: cada `<div key={s.id}>` del mural (~25 líneas de JSX) + `ProctorControls` sidebar (~40 líneas) son inline; `<input type="range">` raw sin `RangeInput`; `<h3>` sueltos. |
| AuditPrivacy.tsx | ~83 | Ítems de audit y DSR inline; `<h3>` sin `SectionTitle`; pequeña pero tiene patrones repetibles. |

## Goals / Non-Goals

**Goals:**

- Extraer `StudentFeedCard`, `ProctorControls` de Proctor.tsx → `screens/admin/components/`
- Extraer `ReviewQueueItem`, `ReviewDecisionPanel` de Revisor.tsx → `screens/admin/components/`
- Extraer `AuditLogItem`, `DsrCard` de AuditPrivacy.tsx → `screens/admin/components/`
- Reemplazar `<input type="range">` raw en Proctor por `RangeInput` (de C-40)
- Reemplazar `<button>` raw "Configurar" en ExamList por `Button size="sm"`
- Reemplazar `<h3>` sueltos en Proctor, AuditPrivacy, Revisor, SessionDetail por `SectionTitle` donde aplique
- Reemplazar barras de progreso inline en Reports por `ProgressBar`
- Colocalizar componentes en `frontend/src/screens/admin/components/` (patrón C-41)
- `groupConsecutiveEvents` mover a un módulo utilitario compartible si Revisor y SessionDetail la necesitan (actualmente solo Revisor; SessionDetail no la usa — mantener local)
- Mantener semántica L2.5: textos de decisión humana inamovibles, disclaimers legales intactos

**Non-Goals:**

- NO tocar AdminDetectionHarness.tsx
- NO modificar `api.ts`, `types.ts`, `store.ts`
- NO cambiar la lógica de cola de revisión, resolución, audit trail ni scores
- NO rediseñar el layout de columnas (el grid lg:grid-cols-3 de Revisor y Proctor ya es correcto)
- NO agregar funcionalidad nueva (exportar dossier, mensajes reales, etc.)
- NO buildear ni commitear

## Decisions

### D-01: Colocalización en `screens/admin/components/`

**Decisión**: misma estructura que `screens/alumno/components/` (C-41). Archivos individuales por componente, nombrados en PascalCase.

**Alternativa descartada**: un único `adminComponents.tsx` con todo barrel-exported — dificulta tree-shaking y búsqueda.

**Componentes a crear**:

```
frontend/src/screens/admin/components/
├── StudentFeedCard.tsx    ← tile de video del mural en Proctor
├── ProctorControls.tsx    ← sidebar de umbral + retos + mensaje
├── ReviewQueueItem.tsx    ← ítem de la cola en Revisor
├── ReviewDecisionPanel.tsx ← panel de resolución con 3 botones
├── AuditLogItem.tsx       ← ítem de audit log en AuditPrivacy
└── DsrCard.tsx            ← tarjeta de derecho del titular (Acceso/Rectificación/etc.)
```

### D-02: Dirección visual por pantalla

**AdminDashboard**:
- `<h3 className="font-headline...">Acciones rápidas</h3>` → `SectionTitle` (sin sub, sin action)
- Botones en acciones rápidas: ya usan `Button` sin `size` (hereda `md`). Cambiar a `size="sm"` — el sidebar card es estrecho, `md` (h-12) es desproporcional.
- Tabla de exámenes: ya bien estructurada. Sin cambios en filas.

**ExamList**:
- `<button onClick={() => editar(e)} className="text-primary...">` → `<Button size="sm" variant="ghost" icon="edit">Configurar</Button>`
- Input de búsqueda: la estructura actual es válida (no usar `FormField` porque es un search inline sin label visible — mantener tal cual).

**Reports**:
- Barras de distribución: `<div className="flex-1 h-6 rounded-full bg-surface-container-high overflow-hidden"><div className="h-full..." style={{width: ...}}>{d.cantidad}</div></div>` → `ProgressBar` (el `ProgressBar` actual es h-2 sin texto interno; aquí se necesita texto con el número — mantener la barra custom pero encapsularla). **Decisión**: `ProgressBar` no admite texto interno (solo colores). Crear wrapping local `SeverityProgressBar` dentro de Reports.tsx — NO extraer a componente global porque es muy específico. La barra actual está bien — solo reemplazar los colores hardcoded `bg-primary-container` por el sistema de colores de `ProgressBar`: usar `tone` según severidad (baseline→neutral→primary, baja→success, media→warning, alta/critica→error). Mantener el número con absoluto/flex porque `ProgressBar` no lo soporta.

**Revisor**:
- `ReviewQueueItem`: extrae el `<button key={s.id}>` con Avatar + datos + Badge de score (43 líneas → componente puro con props `sesion`, `selected`, `onClick`)
- `ReviewDecisionPanel`: extrae el `<div className="bg-surface-container-low...">` con h3 "Resolución...", p disclaimer, 3 botones y link a detalle forense (35 líneas)
- Densidad: el grid `lg:grid-cols-3` está bien. El espaciado `space-y-sm` entre ítems de la cola → `space-y-base` (un toque más de aire).
- `groupConsecutiveEvents` queda en Revisor.tsx (local) — SessionDetail no la necesita.

**SessionDetail**:
- `<h3 className="text-label-sm uppercase...">Eventos discretos</h3>` → `SectionTitle` con `sub={...}` (aprovechar el sub para indicar cuántos eventos hay).
- CadenaPaso ya correcto — sin cambios.

**Proctor**:
- `StudentFeedCard`: extrae el `<div key={s.id} className="rounded-xl overflow-hidden...">` completo (~25 líneas) con todas sus props derivadas de `SesionEnVivo` + `umbral`.
- `ProctorControls`: extrae el sidebar de la columna derecha (`<div className="space-y-lg">` con 2 Cards: controles + mensaje correctivo). Props: `umbral`, `onUmbralChange`, `retos`, `onRetosChange`, `lista`, `mensaje`, `onMensajeChange`, `destinatario`, `onDestinatarioChange`, `onEnviar`.
- `<input type="range">` raw dentro de Proctor → `RangeInput` (de C-40) — solo aplica al range en `ProctorControls` (el range interno del cambio).
- `<h3 className="text-label-md font-bold...">Controles de proctoring</h3>` y `<h3>Mensaje correctivo</h3>` → `SectionTitle` dentro de `ProctorControls`.
- La clase `accent-[#5b5bd6]` en checkbox → `accent-primary` (token del design system).

**AuditPrivacy**:
- `AuditLogItem`: extrae el `<div className="flex items-start gap-sm p-sm...">` con icon + accion + Badge + detalle + ts.
- `DsrCard`: extrae el `<div className="flex items-start gap-sm p-base...">` con icon + titulo + desc (DSR).
- `<h3 className="font-headline text-title-lg...">Derechos del titular</h3>` → `SectionTitle`.

### D-03: Props de componentes extraídos (presentación pura)

Todos los componentes extraídos son **presentación pura**: sin hooks, sin llamadas a api, sin store. Reciben datos y callbacks como props. Esto es el mismo patrón C-41/C-42.

- `StudentFeedCard({ sesion: SesionEnVivo; umbral: number })`
- `ProctorControls({ umbral, onUmbralChange, retos, onRetosChange, lista, mensaje, onMensajeChange, destinatario, onDestinatarioChange, onEnviar })`
- `ReviewQueueItem({ sesion: SesionRevision; selected: boolean; onClick: () => void })`
- `ReviewDecisionPanel({ sesion: SesionRevision; onResolver: (decision, etiqueta) => void; onVerDetalle: () => void })`
- `AuditLogItem({ entrada: { ts, actor, accion, detalle, tono } })`
- `DsrCard({ derecho: { icon, titulo, desc } })`

### D-04: Datos mock en Proctor — "Anatomía I" hardcoded

El Stat "Examen activo" con `value="Anatomía I"` y `sub="Cátedra B · Aula virtual 104"` es un dato de demo coherente con el proyecto (Anatomía es el examen de ejemplo en toda la suite). **No es relleno aspiracional** — es el único examen activo que el demo puede mostrar. Se mantiene tal cual.

### D-05: Tipo local en AuditPrivacy

`AUDITORIA` y `DSR` son arrays de objetos inline tipados con `as const`. Al extraer `AuditLogItem` y `DsrCard`, los tipos de entrada se definen localmente en cada componente (no en `types.ts` — son tipos de presentación, no de dominio).

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| `ReviewDecisionPanel` recibe `onResolver` con firma `(decision: SesionRevision['decision'], etiqueta: string) => void` — acoplamiento a `SesionRevision`. | Aceptable: el panel es específico de la revisión, no pretende ser genérico. |
| `ProctorControls` recibe muchas props (9 props). | Aceptable: es presentación pura; el estado vive en `Proctor.tsx` (orquestador). Alternativa (un objeto `state + handlers`) introduciría un contrato más frágil. |
| `SectionTitle` en todos los `<h3>` puede cambiar el ritmo vertical si hay paddings del Card padre que chocan. | Verificar visualmente en cada pantalla — `SectionTitle` incluye `mb-md` propio; ajustar si hay doble margen. |
| Mover `groupConsecutiveEvents` a un módulo compartido podría ser tentador. | No hacerlo — solo Revisor la usa. YAGNI. |

## Open Questions

- **Ninguna bloqueante para este change.** Los ajustes son de UI/presentación; la lógica subyacente está probada y no cambia.
