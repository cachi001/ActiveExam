## 1. Preparación y estructura

- [x] 1.1 Crear directorio `frontend/src/screens/alumno/components/`
- [x] 1.2 Verificar imports disponibles: `Card`, `Badge`, `Button`, `Icon`, `SectionTitle` de `ui/components`; tipos `Materia`, `Comision`, `Examen`, `Inscripcion` de `lib/types`

## 2. Componente QuickAccessCard

- [x] 2.1 Crear `frontend/src/screens/alumno/components/QuickAccessCard.tsx` con props: `icon: string`, `title: string`, `description: string`, `onClick: () => void`
- [x] 2.2 Layout: botón `w-full flex items-center gap-md p-md bg-surface-container-lowest border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-left`
- [x] 2.3 Ícono: `div w-11 h-11 rounded-xl bg-secondary-container text-on-secondary` con `Icon`
- [x] 2.4 Texto: `p text-label-md font-semibold` para title + `p text-label-sm text-on-surface-variant` para description
- [x] 2.5 Flecha: `Icon name="arrow_forward" className="text-on-surface-variant ml-auto"`

## 3. Componente ExamenProximoCard

- [x] 3.1 Crear `frontend/src/screens/alumno/components/ExamenProximoCard.tsx` con props: `inscripcion: Inscripcion`
- [x] 3.2 Definir `ESTADO_BADGE` (mismo mapa que AlumnoDashboard actual) dentro del componente
- [x] 3.3 Layout: `Card className="flex items-center gap-md"` con ícono `event` en `bg-primary-fixed text-primary rounded-xl w-11 h-11`
- [x] 3.4 Nombre del examen: `p text-label-md font-semibold text-on-surface truncate`
- [x] 3.5 Subtítulo: `nombre_materia · fecha en es-AR (dd Mmm yyyy)`
- [x] 3.6 Badge de estado: `Badge tone={badge.tone} dot`

## 4. Componente ExamenCard

- [x] 4.1 Crear `frontend/src/screens/alumno/components/ExamenCard.tsx` con props: `examen: Examen`, `inscripto: boolean`, `inscribiendo: boolean`, `onInscribir: () => void`
- [x] 4.2 Definir `ESTADO_EXAMEN_LABEL` y `ESTADO_EXAMEN_TONE` dentro del componente
- [x] 4.3 Layout: `Card className="flex items-center gap-md"`
- [x] 4.4 Sección izquierda: nombre del examen (`text-label-md font-semibold`) + fecha + duración (`text-label-sm text-on-surface-variant`)
- [x] 4.5 Sección derecha: badge de estado del examen; si `inscripto` → badge "Inscripto" tone `success`; si `examen.estado === "programado"` y no inscripto → botón "Inscribirme" variant `secondary` size `sm`
- [x] 4.6 Botón en estado `inscribiendo`: spinner `progress_activity` + "Inscribiendo…" + disabled

## 5. Componente ComisionRow

- [x] 5.1 Crear `frontend/src/screens/alumno/components/ComisionRow.tsx` con props: `comision: Comision`, `activa: boolean`, `cargandoExamenes: boolean`, `examenes: Examen[]`, `inscripciones: Inscripcion[]`, `inscribiendoId: string | null`, `onSelect: () => void`, `onInscribir: (examenId: string) => void`
- [x] 5.2 Helper `estaInscripto(examenId: string)` calculado desde `inscripciones`
- [x] 5.3 Encabezado: botón con nombre, docente, horario e ícono `expand_more`/`expand_less`; estilos activo/inactivo iguales al código actual
- [x] 5.4 Contenido expandido: lista de `ExamenCard` con `inscripto={estaInscripto(examen.id)}`, `inscribiendo={inscribiendoId === examen.id}`, `onInscribir={() => onInscribir(examen.id)}`
- [x] 5.5 Estado cargando exámenes: spinner + "Cargando exámenes…"
- [x] 5.6 Estado sin exámenes: texto "No hay exámenes en esta comisión."

## 6. Componente MateriaCard

- [x] 6.1 Crear `frontend/src/screens/alumno/components/MateriaCard.tsx` con props: `materia: Materia`, `activa: boolean`, `cargandoComisiones: boolean`, `comisiones: Comision[]`, `comisionSeleccionada: Comision | null`, `cargandoExamenes: boolean`, `examenes: Examen[]`, `inscripciones: Inscripcion[]`, `inscribiendoId: string | null`, `onSelect: () => void`, `onSelectComision: (c: Comision) => void`, `onInscribir: (examenId: string) => void`
- [x] 6.2 Encabezado: botón con ícono `school`, nombre, código, descripción e ícono `expand_more`/`expand_less`; estilos activo/inactivo iguales al código actual
- [x] 6.3 Contenido expandido (activa): lista de `ComisionRow` con `activa={comisionSeleccionada?.id === comision.id}`, `onSelect={() => onSelectComision(comision)`, y demás props pasadas hacia abajo
- [x] 6.4 Estado cargando comisiones: spinner + "Cargando comisiones…"
- [x] 6.5 Estado sin comisiones: texto "No hay comisiones disponibles."

## 7. Componente InscripcionCard

- [x] 7.1 Crear `frontend/src/screens/alumno/components/InscripcionCard.tsx` con props: `inscripcion: Inscripcion`, `gate: { puede: boolean; codigo?: string; razon?: string } | undefined`, `verificando: boolean`, `onRendir: () => void`, `onCompletarAcuse: () => void`, `onIrAPerfil: () => void`
- [x] 7.2 Definir `ESTADO_CONFIG` (label, tone, icon) dentro del componente
- [x] 7.3 Layout superior: `Card className="space-y-md"` con ícono de estado `w-11 h-11 bg-primary-fixed text-primary rounded-xl`, nombre, materia, fecha, badge
- [x] 7.4 Acción habilitado — gate completo: botón "Rendir" con `icon="play_arrow"` y `disabled={verificando}`; estado verificando: spinner + "Verificando…"
- [x] 7.5 Acción habilitado — acuse faltante: texto + botón "Completar acuse del examen" `icon="assignment_turned_in"` que invoca `onCompletarAcuse`
- [x] 7.6 Acción habilitado — perfil incompleto: texto descriptivo según `codigo` + botón "Renovar biometría" (danger) o "Completar perfil" (outline) que invoca `onIrAPerfil`
- [x] 7.7 Estado rendido: texto "Examen completado." sin botón, con borde superior

## 8. Refactor AlumnoDashboard

- [x] 8.1 Importar `QuickAccessCard` y `ExamenProximoCard` desde `./alumno/components/`
- [x] 8.2 Eliminar el mapa `ESTADO_BADGE` del componente (ya está en `ExamenProximoCard`)
- [x] 8.3 Reemplazar los 3 bloques `<button>` de accesos rápidos por 3 instancias de `QuickAccessCard`
- [x] 8.4 Reemplazar el `.map` de `proximos` por `.map` de `ExamenProximoCard`
- [x] 8.5 Verificar que la pantalla queda en ≤ 120 líneas

## 9. Refactor AlumnoMaterias

- [x] 9.1 Importar `MateriaCard` desde `./alumno/components/`
- [x] 9.2 Eliminar los mapas `ESTADO_EXAMEN_LABEL` y `ESTADO_EXAMEN_TONE` del componente (ya están en `ExamenCard`)
- [x] 9.3 Reemplazar el `.map(materia => ...)` (el bloque JSX completo del árbol) por `.map(materia => <MateriaCard ... />)`
- [x] 9.4 Pasar todas las props necesarias: `activa`, `cargandoComisiones`, `comisiones`, `comisionSeleccionada`, `cargandoExamenes`, `examenes`, `inscripciones`, `inscribiendoId`, `onSelect`, `onSelectComision`, `onInscribir`
- [x] 9.5 Verificar que `iniciarInscripcion` sigue siendo el handler de `onInscribir` (flujo C-26 intacto)
- [x] 9.6 Verificar que la pantalla queda en ≤ 120 líneas

## 10. Refactor AlumnoMisExamenes

- [x] 10.1 Importar `InscripcionCard` desde `./alumno/components/`
- [x] 10.2 Eliminar `ESTADO_CONFIG` del componente (ya está en `InscripcionCard`)
- [x] 10.3 Reemplazar el `.map(insc => ...)` por `.map(insc => <InscripcionCard ... />)`
- [x] 10.4 Pasar todas las props: `inscripcion={insc}`, `gate={gatesPorExamen[insc.examen_id]}`, `verificando={verificandoId === insc.id}`, `onRendir={() => handleRendir(insc)}`, `onCompletarAcuse={() => setExamenCompletandoAcuse(insc.examen_id)}`, `onIrAPerfil={() => navigate('/alumno/perfil')}`
- [x] 10.5 Verificar que la pantalla queda en ≤ 110 líneas

## 11. Refinamiento visual Login

- [x] 11.1 Ajustar whitespace del header de la card: aumentar `gap-md` → `gap-lg` entre ícono y textos si el resultado visual lo requiere
- [x] 11.2 Agregar sigla institucional visible: subtítulo `text-label-md text-on-surface-variant` con `INSTITUTION.sigla` (o derivar de `INSTITUTION.facultad`) si no está ya visible
- [x] 11.3 Revisar microcopy de privacidad en `<nav>`: condensar si tiene más de una línea visible
- [x] 11.4 Verificar que el botón CTA tiene `size="lg"` y `w-full` (ya presente en C-40; no cambiar)
- [x] 11.5 Confirmar que el footer de privacidad (Ley 25.326) es una sola línea `text-label-sm`

## 12. Verificación E2E visual

- [x] 12.1 Navegar a `/login` — verificar layout centrado, branding institucional, CTA prominente, sin campos de texto
- [x] 12.2 Login mock → `/alumno/dashboard` — verificar saludo, banner de perfil (si aplica), accesos rápidos con `QuickAccessCard`, exámenes próximos con `ExamenProximoCard`
- [x] 12.3 Navegar a `/alumno/materias` — verificar árbol de acordeón, selección materia → comisiones → exámenes, botón "Inscribirme" → flujo acuse C-26
- [x] 12.4 Navegar a `/alumno/mis-examenes` — verificar lista de `InscripcionCard`, banner de gate C-26 (si aplica), botón "Rendir" / "Completar acuse"
- [x] 12.5 Verificar responsive (sm breakpoint): grilla de accesos rápidos 1→2 cols, cards apiladas en mobile
