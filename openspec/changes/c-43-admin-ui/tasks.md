## 1. Estructura de directorios

- [ ] 1.1 Crear directorio `frontend/src/screens/admin/components/` (colocalización igual que `alumno/components/`)

## 2. AdminDashboard — ajustes inline

- [ ] 2.1 En `AdminDashboard.tsx`: reemplazar `<h3 className="font-headline text-title-lg text-on-surface">Acciones rápidas</h3>` por `<SectionTitle>Acciones rápidas</SectionTitle>` (sin sub, sin action)
- [ ] 2.2 En `AdminDashboard.tsx`: cambiar los tres `<Button>` del card de acciones rápidas a `size="sm"` (Crear examen, Ver reportes, Auditoría)
- [ ] 2.3 Verificar que la tabla de exámenes mantiene la jerarquía visual correcta (`font-semibold` en nombre, `text-label-sm text-on-surface-variant` en cátedra+inscriptos) — sin cambio de código si ya está correcto

## 3. ExamList — Button inline

- [ ] 3.1 En `ExamList.tsx`: reemplazar `<button onClick={() => editar(e)} className="text-primary hover:underline text-label-md inline-flex items-center gap-base"><Icon name="edit" ... /> Configurar</button>` por `<Button size="sm" variant="ghost" icon="edit" onClick={() => editar(e)}>Configurar</Button>`
- [ ] 3.2 Agregar import de `Button` si no está ya (verificar imports al inicio del archivo)

## 4. Reports — tono semántico en barras

- [ ] 4.1 En `Reports.tsx`: definir un mapa local `SEV_TONE` que mapee `Severidad` → `'primary' | 'success' | 'warning' | 'error'` (baseline→primary, baja→success, media→warning, alta→error, critica→error)
- [ ] 4.2 En `Reports.tsx`: reemplazar el `<div className="flex-1 h-6 rounded-full bg-surface-container-high overflow-hidden"><div ... style={{width: ...}}>{d.cantidad}</div></div>` por una versión que use el tono semántico correcto via `SEV_TONE[d.severidad]` — manteniendo el número visible dentro de la barra (la barra custom conserva altura h-6 y texto interno; el `ProgressBar` de components.tsx no soporta texto interno así que se mantiene el div custom pero con el color semántico)

## 5. AuditLogItem — componente extraído

- [ ] 5.1 Crear `frontend/src/screens/admin/components/AuditLogItem.tsx` — componente de presentación pura con prop `entrada: { ts: string; actor: string; accion: string; detalle: string; tono: 'error' | 'neutral' | 'warning' | 'success' | 'primary' }`; extrae el JSX del `<div className="flex items-start gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/30">` de AuditPrivacy
- [ ] 5.2 Importar `Icon`, `Badge` de `../../../ui/components` en `AuditLogItem.tsx`

## 6. DsrCard — componente extraído

- [ ] 6.1 Crear `frontend/src/screens/admin/components/DsrCard.tsx` — componente de presentación pura con prop `derecho: { icon: string; titulo: string; desc: string }`; extrae el JSX del `<div className="flex items-start gap-sm p-base rounded-xl bg-surface-container-low border border-outline-variant/30">` de AuditPrivacy
- [ ] 6.2 Importar `Icon` de `../../../ui/components` en `DsrCard.tsx`

## 7. AuditPrivacy — refactor con componentes y SectionTitle

- [ ] 7.1 En `AuditPrivacy.tsx`: reemplazar `<h3 className="font-headline text-title-lg text-on-surface">Derechos del titular</h3><p className="text-label-sm text-on-surface-variant">Ley 25.326 · AAIP</p>` por `<SectionTitle sub="Ley 25.326 · AAIP">Derechos del titular</SectionTitle>`
- [ ] 7.2 En `AuditPrivacy.tsx`: reemplazar el map inline de entradas de auditoría por `{AUDITORIA.map((a, i) => <AuditLogItem key={i} entrada={a} />)}`
- [ ] 7.3 En `AuditPrivacy.tsx`: reemplazar el map inline de derechos DSR por `{DSR.map((d) => <DsrCard key={d.titulo} derecho={d} />)}`
- [ ] 7.4 Agregar imports de `SectionTitle`, `AuditLogItem`, `DsrCard` en `AuditPrivacy.tsx`; verificar que `Icon` ya no se usa directamente (movido a sub-componentes)

## 8. ReviewQueueItem — componente extraído

- [ ] 8.1 Crear `frontend/src/screens/admin/components/ReviewQueueItem.tsx` — componente puro con props `sesion: SesionRevision`, `selected: boolean`, `onClick: () => void`; extrae el JSX del `<button key={s.id} onClick={() => setSel(s)} ...>` de Revisor.tsx incluyendo Avatar + nombre + score + examen + fecha + id + incidencias
- [ ] 8.2 Importar `Avatar`, `Badge`, `Icon` de `../../../ui/components` y tipo `SesionRevision` de `../../../lib/types` en `ReviewQueueItem.tsx`

## 9. ReviewDecisionPanel — componente extraído

- [ ] 9.1 Crear `frontend/src/screens/admin/components/ReviewDecisionPanel.tsx` — componente puro con props `sesion: SesionRevision`, `onResolver: (decision: SesionRevision['decision'], etiqueta: string) => void`, `onVerDetalle: () => void`; extrae el bloque `<div className="bg-surface-container-low rounded-xl p-md space-y-md border border-outline-variant/40">` con h3 "Resolución...", disclaimer, 3 botones y link "Ver detalle forense completo"
- [ ] 9.2 Importar `Button`, `Icon` de `../../../ui/components` y tipo `SesionRevision` de `../../../lib/types` en `ReviewDecisionPanel.tsx`; importar `Term` de `../../../ui/Term`
- [ ] 9.3 Asegurar que el disclaimer "El software no sanciona automáticamente. Tu decisión es obligatoria y queda en el audit log inmutable." está presente e inamovible en el componente

## 10. Revisor — refactor con componentes y SectionTitle

- [ ] 10.1 En `Revisor.tsx`: reemplazar `<h2 className="font-headline text-title-lg text-on-surface">Cola de sesiones</h2>` por `<SectionTitle>Cola de sesiones</SectionTitle>` (o mantener el `flex items-center justify-between` como wrapper propio si SectionTitle no soporta el Badge inline como action)
- [ ] 10.2 En `Revisor.tsx`: cambiar `space-y-sm` entre ítems de la cola por `space-y-base` para mayor separación
- [ ] 10.3 En `Revisor.tsx`: reemplazar el map `{cola.map((s) => (<button key={s.id} ...>...</button>))}` por `{cola.map((s) => <ReviewQueueItem key={s.id} sesion={s} selected={sel?.id === s.id} onClick={() => setSel(s)} />)}`
- [ ] 10.4 En `Revisor.tsx`: reemplazar el `<h3>` "Línea de tiempo de anomalías" por `<SectionTitle sub={`${sel.eventos.length} incidencias`}>Línea de tiempo de anomalías</SectionTitle>`
- [ ] 10.5 En `Revisor.tsx`: reemplazar el `<h3>` "Evidencia y cadena de custodia" por `<SectionTitle>Evidencia y <Term termKey="cadena_de_custodia">cadena de custodia</Term></SectionTitle>` (o wrapper adecuado)
- [ ] 10.6 En `Revisor.tsx`: reemplazar el bloque de resolución `<div className="bg-surface-container-low ...">` por `<ReviewDecisionPanel sesion={sel} onResolver={resolver} onVerDetalle={() => { setRevision(sel); navigate('/revisor/detalle'); }} />`
- [ ] 10.7 Agregar imports de `SectionTitle`, `ReviewQueueItem`, `ReviewDecisionPanel` en `Revisor.tsx`; verificar que `Badge`, `Avatar` ya no se usan directamente en `Revisor.tsx` (movidos a sub-componentes)

## 11. StudentFeedCard — componente extraído

- [ ] 11.1 Crear `frontend/src/screens/admin/components/StudentFeedCard.tsx` — componente puro con props `sesion: SesionEnVivo`, `umbral: number`; extrae el JSX del `<div key={s.id} className="rounded-xl overflow-hidden border bg-inverse-surface relative aspect-video ...">` completo de Proctor.tsx incluyendo la imagen, overlay de nombre, ScoreChip, última señal, legajo y badge de escalado
- [ ] 11.2 Importar `Icon`, `ScoreChip` de `../../../ui/components` y tipo `SesionEnVivo` de `../../../lib/types` en `StudentFeedCard.tsx`

## 12. ProctorControls — componente extraído

- [ ] 12.1 Crear `frontend/src/screens/admin/components/ProctorControls.tsx` — componente puro con props: `umbral: number`, `onUmbralChange: (v: number) => void`, `retos: string[]`, `onRetosChange: (ids: string[]) => void`, `lista: SesionEnVivo[]`, `mensaje: string`, `onMensajeChange: (v: string) => void`, `destinatario: string`, `onDestinatarioChange: (v: string) => void`, `onEnviar: () => void`; extrae el `<div className="space-y-lg">` con los dos Cards de la columna derecha de Proctor.tsx
- [ ] 12.2 En `ProctorControls.tsx`: usar `RangeInput` (de `../../../ui/components`) para el control de umbral con `min={30} max={90} label="Umbral de cola de revisión" unit="%"`
- [ ] 12.3 En `ProctorControls.tsx`: usar `SectionTitle` para los encabezados "Controles de proctoring" y "Mensaje correctivo"
- [ ] 12.4 En `ProctorControls.tsx`: cambiar `accent-[#5b5bd6]` en checkboxes por `accent-primary`
- [ ] 12.5 Importar `Button`, `SectionTitle`, `RangeInput` de `../../../ui/components`; importar `DESAFIOS` de `../../../lib/api`; importar tipo `SesionEnVivo` de `../../../lib/types`

## 13. Proctor — refactor con componentes y SectionTitle

- [ ] 13.1 En `Proctor.tsx`: reemplazar el `<h3 className="text-label-md font-bold ...">` de ProctorControls inline → eliminado (queda en `ProctorControls`)
- [ ] 13.2 En `Proctor.tsx`: reemplazar el map `{lista.map((s) => (<div key={s.id} ...>...</div>))}` por `{lista.map((s) => <StudentFeedCard key={s.id} sesion={s} umbral={umbral} />)}`
- [ ] 13.3 En `Proctor.tsx`: reemplazar el `<div className="space-y-lg">` de la columna derecha por `<ProctorControls umbral={umbral} onUmbralChange={setUmbral} retos={retos} onRetosChange={setRetos} lista={lista} mensaje={mensaje} onMensajeChange={setMensaje} destinatario={destinatario} onDestinatarioChange={setDestinatario} onEnviar={enviar} />`
- [ ] 13.4 Agregar imports de `StudentFeedCard`, `ProctorControls` en `Proctor.tsx`; verificar que `DESAFIOS` ya no se importa directamente en Proctor.tsx (movido a ProctorControls); verificar que `Button`, `ScoreChip` ya no son necesarios en Proctor.tsx

## 14. SessionDetail — SectionTitle en eventos

- [ ] 14.1 En `SessionDetail.tsx`: reemplazar `<h3 className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40 pb-base">Eventos discretos</h3>` por `<SectionTitle sub={`${sel.eventos.length} evento${sel.eventos.length !== 1 ? 's' : ''}`}>Eventos discretos</SectionTitle>`
- [ ] 14.2 Agregar import de `SectionTitle` en `SessionDetail.tsx` si no está ya

## 15. Verificación final

- [ ] 15.1 Ejecutar `tsc --noEmit` desde `frontend/` y confirmar 0 errores
- [ ] 15.2 Verificar visualmente (manual o Playwright) que las 7 pantallas admin se ven correctas: AdminDashboard, ExamList, Reports, Revisor, SessionDetail, Proctor, AuditPrivacy
- [ ] 15.3 Confirmar que AdminDetectionHarness.tsx no fue modificado (verificar git diff)
- [ ] 15.4 Confirmar que `api.ts`, `types.ts`, `store.ts` no fueron modificados
- [ ] 15.5 Ejecutar `openspec validate --strict` y confirmar OK
