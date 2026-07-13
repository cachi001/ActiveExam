## Context

La inscripción por código (C-70) existe pero es decorativa: no filtra el catálogo ni gatea la rendición. Estado real verificado en prod:
- `listar_examenes_contenido` (exam_content/router.py:1266) lista todo el catálogo sin filtrar por inscripción.
- `puede_rendir` (inscripcion_service.py:251) = `consentimiento_vigente AND biometria_vigente`; la inscripción "solo set-membership" (router.py:1309).
- `crear_sesion` (proctoring/sessions/router.py) valida ventana + intentos vía `verificar_enforcement`, no inscripción.

Piezas reutilizables: tabla `inscripcion` (`usuario_id` ↔ `comision_id`, C-70), FK `examen_contenido.comision_id`, `InscripcionService`, y `usuario.id_institucional` (identidad del principal en el flujo de rendición).

Nota de identidad: `inscripcion.usuario_id` es el UUID de `usuario`, pero el flujo de rendición identifica al alumno por `id_institucional` (JWT). Toda verificación de inscripción resuelve `id_institucional → usuario.id` (JOIN con `usuario`) — igual criterio que el resto del backend.

**Gobernanza**: control de acceso a exámenes. Reglas duras: cliente no confiable (#6), tests sin mocks de DB (#4), Pydantic `extra='forbid'` (#5), snake_case (#6), sin hardcodes.

## Goals / Non-Goals

**Goals:**
- La inscripción a materia+comisión es condición de acceso: sin ella, el alumno no ve ni puede rendir el examen.
- Filtrar server-side "Mis materias" y "Exámenes disponibles" por las inscripciones del alumno.
- Gate de rendición doble (perfil ∧ inscripción), enforced server-side, con backstop en `crear_sesion`.
- Cero hardcode: todo desde `inscripcion` real.

**Non-Goals:**
- No cambiar el mecanismo de matriculación por código (C-70 queda igual).
- No tocar el gate de perfil (consentimiento + biometría) — solo se le SUMA la condición de inscripción.
- No agregar migración (la tabla `inscripcion` ya existe).
- Sin relación con el acuse por-examen (eliminado). Este slice (gate de inscripción) es la PRIMERA parte de C-71; la Cola de Revisión y las Sesiones Grabadas son slices posteriores del mismo change (se especifican al encararlos).

## Decisions

### D1 — Filtrar el catálogo server-side por comisiones inscriptas (rol estudiante)
`listar_examenes_contenido` recibe el `principal`. Para rol estudiante, se hace JOIN `examen_contenido → comision → inscripcion` filtrando por `inscripcion.usuario_id = (usuario del principal)`. El rol admin conserva la vista completa (branch por rol). El filtro vive en SQL (`ExamenContenidoSqlRepository`), no en el cliente. **Alternativa descartada**: filtrar en el frontend → burlable, y el catálogo igual expondría todo por la API.

### D2 — "Mis materias" derivado de `inscripcion`
La fuente de "Mis materias" pasa a ser las comisiones inscriptas del alumno (`SELECT ... FROM inscripcion JOIN comision JOIN materia WHERE usuario_id = ?`). Sin inscripciones → lista vacía + CTA a matricularse por código. **Alternativa descartada**: listar todas las materias/comisiones → es el bug actual.

### D3 — Sumar la condición de inscripción al gate `puede_rendir`
El gate pasa de `perfil_completo` a `perfil_completo AND inscripto_en(comision_del_examen)`. Se agrega una consulta de existencia en `inscripcion` para `(usuario_id, examen.comision_id)`. Nueva razón `no_inscripto` cuando el perfil está OK pero falta la inscripción. **Alternativa descartada**: gate solo por perfil → deja el agujero abierto.

### D4 — Backstop server-side en `crear_sesion`
Junto a `verificar_enforcement`, cuando `body.examen_contenido_id` está presente, se verifica que el alumno esté inscripto en la comisión de ese examen; si no, **403 `no_inscripto`** (mismo estilo que `fuera_de_ventana`). Es el candado duro: el filtrado del catálogo es UX; esto es enforcement. **Alternativa descartada**: confiar solo en el filtrado del catálogo → el cliente no es confiable (regla #6).

### D5 — Frontend consume lo ya filtrado
`misMaterias`/`listarExamenesContenido`/`puedeRendir` no re-filtran: muestran lo que el backend devuelve. Mis Materias y Mis Exámenes muestran estado vacío coherente ("no estás inscripto en ninguna materia — matriculate con un código"). El código de la razón `no_inscripto` se refleja en la card con CTA a matricularse.

## Risks / Trade-offs

- **[Identidad id_institucional vs usuario_id]** El flujo tiene `id_institucional`, `inscripcion` usa UUID → resolver con JOIN `usuario`. Mitigación: un solo punto de resolución reutilizable; testear que resuelve correctamente.
- **[Admin/otros roles]** El filtrado por inscripción aplica SOLO a estudiantes; admin/proctor conservan la vista completa. Mitigación: branch explícito por rol, con test de que admin ve todo.
- **[Datos demo]** Los estudiantes seed hoy no están inscriptos → tras este cambio no verían el examen demo. Mitigación (decisión aparte): que el seed matricule los EST-00x a C1, o que se auto-matriculen con `PROG1-C1`.
- **[Exámenes sin comisión]** Si algún `examen_contenido` tuviera `comision_id` NULL, definir política (no visible para alumnos por defecto). Documentar en implementación.

## Migration Plan

1. Sin migración de esquema (usa `inscripcion` existente).
2. Deploy backend: catálogo filtrado + gate + backstop.
3. Deploy frontend: estados vacíos + CTA matricularse.
4. **Seed/datos**: decidir si los EST-00x se matriculan a C1 (para que el demo siga visible). Rollback: revertir el filtro deja el catálogo abierto como hoy (sin pérdida de datos).

## Open Questions

- ¿Los estudiantes seed se auto-matriculan a C1 en el seed, o se los deja sin inscripción (y el demo requiere matricularse con `PROG1-C1`)?
- Política para `examen_contenido.comision_id` NULL (exámenes “sueltos”): ¿ocultos para alumnos?
- ¿El admin/proctor necesita en algún caso la vista filtrada, o siempre completa?
