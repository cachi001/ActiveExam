> **Estructura por slices.** Las secciones **Context → Migration Plan** de abajo son el diseño del **Slice 1 (gate de inscripción)**, ya **implementado y commiteado** (`cd076f8`). Se conservan como registro. El **Slice 2 (Cola de Revisión + transparencia al alumno)** se diseña en la sección **"Slice 2"** al final de este documento.

# Slice 1 — Gate de inscripción (HECHO, commit `cd076f8`)

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

---

# Slice 2 — Cola de Revisión + transparencia al alumno (EN PLANIFICACIÓN)

## Context (Slice 2)

Estado real verificado:
- **Modelo de decisión (backend).** `backend/app/domain/review/decision.py` ya define `DecisionTerminal = pendiente | descartada | escalada | derivada` (RN-RV-05). `ReviewDecisionService` (`application/review/service.py`) persiste la decisión y la trata como **INMUTABLE** (RN-RV-07): un segundo `decide` → `DecisionAlreadyMadeError` → 409. Cada decisión (y cada intento rechazado) se auditea con propósito.
- **Modelo de decisión (frontend).** `frontend/src/lib/types.ts` (~L519) tiene un modelo DISTINTO y plano: `DecisionRevisor = aprobado | flaggeado_para_sumario | sin_hallazgos | pendiente`. `ColaPanelDecision.tsx` expone 3 botones. **Hay un gap semántico** entre front (aprobado/flaggeado/sin_hallazgos) y back (descartada/escalada/derivada) que slice 2 debe cerrar con un modelo único.
- **Permisos.** No existe capa de capacidades: el gating es puramente por rol (`require_roles(Rol.REVISOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA, Rol.PROCTOR)` en `review/router.py`). El enum `Rol` (`domain/auth/roles.py`) NO tiene un rol de "dirección académica" / autoridad disciplinaria separada.
- **Nota / calificación.** No hay tabla de `nota`/grade formal. La "nota" del MVP es el resultado válido de la rendición asociado a la sesión; "anular la nota" = marcar ese resultado como anulado (acto de resolución), no borrar un registro.

Piezas reutilizables: `ReviewDecisionService` + su patrón de audit con propósito, el `require_roles`/`AuthenticatedPrincipal`, el detalle de sesión (`SesionProctoringDetalle` con eventos + biometría re-inferida server-side), la migración 0013 (columnas `decision*` en `proctoring_session`).

**Gobernanza: ALTO/CRÍTICO** (notas + disciplina + audit). Reglas duras: #5 (nunca sanción automática — el humano decide), #6 (server-side, cliente no confiable), #7 (Ley 25.326 + audit del acceso del titular); código: `extra='forbid'`, snake_case, PascalCase, tests sin mocks de DB.

## Goals / Non-Goals (Slice 2)

**Goals:**
- Modelo de decisión único de **dos fases** (revisar → resolver), reconciliando front y back.
- El **veredicto** (anular la nota / descartar el caso) como acto separado, gateado por capacidad `resolver_caso` server-side, con motivo + evidencia obligatorios y audit inmutable.
- **Reversibilidad** del efecto de la anulación (acto compensatorio), notificada al alumno — como HOOK para c-18.
- **Transparencia al alumno**: ve su evidencia re-inferida, el análisis por señal, la decisión y el motivo; el acceso del titular queda auditado.
- Separación de capacidad **diseñada** (capability→roles config-driven) aunque **desplegada con concentración** (hoy todo lo tiene el revisor).

**Non-Goals:**
- **NO** construir el flujo de apelación formal ni la verificación de cadena de custodia end-to-end → `c-18`. Slice 2 solo deja el hook (reversible + notificado).
- **NO** Sesiones Grabadas (slice 3).
- **NO** introducir un rol nuevo en el enum `Rol` ahora (la remapeabilidad de `resolver_caso` se resuelve por config del map de capacidades, sin tocar el enum ni los routers).
- **NO** re-infierir/re-hashear evidencia nueva: se reusa lo que el pipeline ya produce server-side (regla #6 ya satisfecha aguas arriba); transparencia solo lo EXPONE al titular.

## Decisions (Slice 2)

### D6 — Modelo de decisión de dos fases (revisar → resolver), unificado front/back
Un solo modelo canónico, en dos fases:

- **Fase 1 — Revisión (capacidad `revisar_sesion`, el revisor):**
  - `sin_hallazgos` — falso positivo; **valida la nota**. (terminal de revisión)
  - `aprobado` — señales revisadas, se consideran legítimas; **valida la nota**. (terminal de revisión)
  - `caso_abierto` — **derivación**: hay algo que resolver; deja el caso ABIERTO para la fase 2. (NO valida ni anula todavía)
- **Fase 2 — Resolución (capacidad `resolver_caso`, la autoridad):** solo aplicable si el caso está `caso_abierto`.
  - `anulado_por_fraude` — **anula la nota**. (veredicto)
  - `caso_descartado` — cierra el caso **validando la nota** (no había fraude tras resolver).

**Mapeo exacto desde el enum backend existente** (`DecisionTerminal` en `domain/review/decision.py:9` = `pendiente | descartada | escalada | derivada`; prod slim tiene ~0 filas decididas):

| Valor viejo persistido | Valor nuevo | Nota |
|------------------------|-------------|------|
| `pendiente` | `pendiente` | estado inicial, sin cambio |
| `descartada` | `sin_hallazgos` | falso positivo, valida la nota |
| `derivada` | `caso_abierto` | derivó, sin resolver aún |
| `escalada` | `caso_abierto` | **`escalada` se DROPEA** del modelo (no tiene downstream); las filas existentes se mapean a `caso_abierto` |

**`escalada` se elimina** del enum unificado: no tenía consumidor aguas abajo (no cablea nada). "Escalar a otra autoridad" queda cubierto por la separación de capacidad (D8): el caso `caso_abierto` lo resuelve quien tenga `resolver_caso`, sea el mismo revisor u otra autoridad. El front (`DecisionRevisor`, `lib/types.ts`) adopta este modelo único, cerrando el gap.

**Justificación:** un modelo plano no puede expresar "revisado pero aún sin veredicto"; las dos fases hacen explícito el punto donde entra el permiso `resolver_caso` y el punto donde la nota efectivamente cambia. **Alternativa descartada:** enriquecer solo con `anulado_por_fraude` en un modelo plano → funde revisión y veredicto, rompe la baranda (a) y la separación de capacidad.

### D7 — `flaggeado_para_sumario` se reencuadra como `caso_abierto`, NO se funde con `anulado_por_fraude`
Se elige **dejarlo como estado "caso abierto, aún sin resolver"** (`caso_abierto`), no fusionarlo con la anulación.

**Justificación:** fusionarlos colapsaría el acto de **revisar/derivar** (bajo `revisar_sesion`) con el acto de **resolver/anular** (bajo `resolver_caso`), violando la baranda (a) "acto separado y explícito" y la separación de capacidad. El revisor **deriva** (abre el caso); la autoridad **resuelve** (anula o descarta). Que hoy sea la misma persona (concentración) es una decisión de *deployment*, no de *modelo*. **Alternativa descartada:** un solo `anulado_por_fraude` que reemplace a `flaggeado` → imposibilita "diseñar para separación, desplegar con concentración".

### D8 — Capa de capacidades config-driven (capability → roles), reemplaza el `require_roles` hardcodeado
Se introduce un módulo de dominio `permissions`/`capabilities` que mapea **capacidad → conjunto de roles**, como dato de config (mismo espíritu que `ROLES_CON_MFA` en `roles.py`):

```
CAPABILITY_ROLES = {
  "revisar_sesion":  {REVISOR, COORDINADOR, ADMIN_SISTEMA},
  "resolver_caso":   {REVISOR},   # HOY: concentración. Remapeable por config.
}
```

Los routers pasan de `require_roles(Rol.X, ...)` a `require_capability("resolver_caso")`. **Mañana**, asignar `resolver_caso` a otra autoridad (p. ej. agregar un futuro rol de Dirección académica al set, o mover el set) es un cambio de **config del map**, sin tocar endpoints ni lógica.

**Justificación:** ancla en KB `03` (revisor "deriva"; decisión disciplinaria final = Dirección académica; RACI). Cumple el lema "diseñar para separación, desplegar con concentración". **Alternativa descartada:** seguir con `require_roles` por endpoint → cualquier reasignación futura obliga a refactor de routers.

### D9 — Endpoint de resolución (`resolver_caso`) separado del `decide` de revisión (baranda a)
La anulación/descarte NO reusa el `POST /review/session/{id}/decide`. Se agrega un **acto explícito y distinto**, p. ej. `POST /review/session/{id}/resolve`, gateado por `require_capability("resolver_caso")`, que:
- exige `caso_abierto` como precondición (409 si no está abierto),
- exige `motivo` no vacío + `evidencia` adjunta (400 si falta) — baranda (b),
- registra el acto en el audit log inmutable, con propósito, **distinguiéndolo del acto de revisar** (RN-RV-06),
- aplica el efecto sobre la nota (validada/anulada).

El gate se valida **server-side** aunque el front oculte el botón (regla #6, backstop). **Alternativa descartada:** un flag `anular=true` en el `decide` existente → no es "acto separado", viola baranda (a) y mezcla capacidades.

### D10 — La "nota" es un estado de resolución sobre `proctoring_session`, proyectado a `MiNota`; NO se toca `moodle_writeback_estado`
No existe tabla `ResultadoExamen`. La nota académica vive en `moodle_writeback_estado.nota` (`moodle_writeback.py:94`), y la decisión del revisor **ya** vive en `proctoring_session.decision*` (columnas de la migración 0013). La resolución (`anulado_por_fraude` / `caso_descartado`) se agrega como **estado nuevo sobre `proctoring_session`** (junto a `decision`), **NO** sobre la tabla de Moodle. La nota **no se borra**: se **invalida** (reversible). El write-back a Moodle NO se muta desde la resolución; en cambio, su **envío se gatea por estado de revisión** (ver D15 — IN-SCOPE).

**Alternativa descartada:** crear una entidad `ResultadoExamen` o mutar `moodle_writeback_estado` → sobre-ingeniería y acoplaría la anulación a la sanción académica externa (que no se automatiza).

### D10b — Inmutabilidad + reversibilidad vía acto compensatorio append-only en el audit_log EXISTENTE (baranda d, hook c-18)
Tensión: RN-RV-06/07 exigen registros **inmutables** (cadena de custodia); la baranda (d) exige que la anulación sea **reversible**. Se reconcilia reutilizando el **audit_log existente** (`audit_log.py:20`: hash-chain + trigger de inmutabilidad Postgres + propósito declarado), que review ya usa vía `SqlReviewAuditor.log_decision` (`review.py:80`). **Cero infra nueva.**

Cada acto (revisión, resolución, reversión) es una entrada **append-only**; **nunca un UPDATE** ni un borrado. El estado actual de la nota se **deriva del último acto** sobre la sesión. Revertir una anulación = **nueva entrada append-only** (`nota_restituida`) con su propósito, que restituye la nota — el acto de anulación original permanece intacto.

Slice 2 implementa: (1) la anulación reversible-por-diseño (el efecto se deriva, no se hornea), (2) la exposición del veredicto al alumno por **pull** (ver D11b). Slice 2 **NO** implementa el flujo de apelación que dispara la reversión — eso es `c-18`. El hook que c-18 consume: existe el acto compensatorio append-only y la nota es derivada, así que c-18 solo emite el acto de reversión tras una apelación exitosa. **Alternativa descartada:** UPDATE del registro de anulación al revertir → rompe inmutabilidad/cadena de custodia (RN-RV-06).

### D11b — Notificación al alumno = PULL vía `MiNota`, sin infra nueva
No hay canal push (ni mail). El alumno hace **pull** de `GET /mis-notas` (`exam_content/router.py:1460` → `MiNota`, `application/moodle/resultados_query.py:232`; `MiNota` ya expone `en_cola_revision`). Se **proyecta el veredicto en `MiNota`**: cuando la resolución = `anulado_por_fraude`, `MiNota` expone el veredicto + acceso al **informe de devolución** (D12). Si la resolución es `caso_descartado` / `sin_hallazgos` / `aprobado` → `MiNota` **NO** expone evidencia (minimización). **Alternativa descartada:** montar un canal de notificaciones push/email → infra nueva innecesaria para el hook.

### D14 — NO cablear `caso_disciplinario`
La tabla `caso_disciplinario` existe (`transactional.py:234`) pero está **desconectada**. Slice 2 **NO la cablea**: `caso_abierto` significa "derivó, sin resolver aún" y vive como estado sobre `proctoring_session`. Conectar `caso_disciplinario` es un change futuro, fuera de scope. **Alternativa descartada:** cablear la tabla ahora → arrastra scope disciplinario formal que pertenece a otro change.

### D11 — Motivo obligatorio en toda decisión; evidencia obligatoria en la anulación
`observaciones`/`motivo` pasa de opcional a **requerido y no vacío** en TODA decisión (fase 1 y 2). La anulación (`anulado_por_fraude`) exige además **evidencia adjunta** (referencia a la evidencia de la sesión). Validación server-side (Pydantic `extra='forbid'`, campo requerido); el front lo refuerza (no habilita el submit sin motivo). **Alternativa descartada:** motivo opcional → un veredicto sin fundamento no es auditable (RN-RV-06, baranda b).

### D12 — Transparencia al alumno (informe de devolución): SOLO cuando la resolución es `anulado_por_fraude`
El "informe de devolución" es **disclosure de debido proceso**: se muestra al alumno **únicamente** cuando su nota fue **anulada por fraude** (`anulado_por_fraude`). En ese caso el alumno ve, scoped a su **propia sesión** (RBAC: estudiante solo su sesión, KB `03`): capturas vía **URL firmada 15 min** (KB `03`), el análisis por señal (qué dijo cada detector, re-inferido server-side — NO el buffer del cliente, regla #6), la decisión y el motivo. Si la sesión se **descartó** (`caso_descartado`), nunca se flaggeó, o terminó en `sin_hallazgos`/`aprobado` → el alumno **NO** ve el volcado de evidencia (**minimización**, Ley 25.326). Cada acceso del **titular** al informe se registra en el audit log como ejercicio del **derecho de acceso** (Ley 25.326, RN-DSR-01). Nueva pantalla React (PascalCase) que consume el endpoint scoped, alcanzable desde `MiNota` cuando hay veredicto de anulación. **Alternativa descartada:** exponer la evidencia siempre que hubo revisión → viola minimización (Ley 25.326); mostrar el buffer local del cliente → viola regla #6.

### D13 — La anulación de la nota NO es sanción automática (regla #5)
El **score solo prioriza** la cola; jamás dispara `anulado_por_fraude`. La transición a `anulado_por_fraude` SOLO ocurre por un acto humano explícito de quien tiene `resolver_caso`. No hay ningún path automático desde un score/umbral hacia la anulación. Esto se testea explícitamente (no existe transición sistema→anulado). **Alternativa descartada:** auto-anular sobre cierto score → viola frontalmente la regla dura #5.

## Risks / Trade-offs (Slice 2)

- **[Migración del modelo de decisión]** Cambiar el enum y los valores persistidos (0013) puede romper decisiones existentes. Mitigación: migración con mapeo explícito (D6) en dos pasos (Alembic destructivo en dos pasos), tests de datos existentes.
- **[Front/back desincronizados]** El gap actual de labels es fuente de bugs. Mitigación: un solo modelo canónico (D6); el front deriva labels de los valores del back.
- **[Concentración de poder hoy]** Que el revisor tenga `resolver_caso` concentra revisar+resolver. Aceptado como decisión de deployment; mitigado por barandas (a–d) y por el diseño remapeable (D8) que permite separar sin refactor.
- **[Inmutabilidad vs reversibilidad]** Riesgo de implementar la reversión como UPDATE. Mitigación: D10 append-only, test que verifica que revertir NO muta el acto de anulación.
- **[Alcance que se filtra a c-18]** Tentación de construir la apelación acá. Mitigación: frontera explícita; slice 2 solo deja el hook.

## Migration Plan (Slice 2)

1. Migración Alembic (dos pasos): **estado de resolución sobre `proctoring_session`** (`anulado_por_fraude` / `caso_descartado`, junto a `decision`) + mapeo de valores del enum viejo (D6: `descartada→sin_hallazgos`, `derivada→caso_abierto`, `escalada→caso_abierto`, drop `escalada`). **Sin** tabla nueva de actos: la reversibilidad usa el `audit_log` existente (D10b). **NO** se toca `moodle_writeback_estado`.
2. Backend: capa de capacidades (D8) → gating por capacidad en review router; endpoint `resolve` (D9); motivo/evidencia obligatorios (D11); proyección del veredicto en `MiNota` (D11b); endpoint de informe de devolución gated por `anulado_por_fraude` (D12); actos append-only en el `audit_log` existente distinguiendo revisar/resolver/revertir (D10b).
3. Frontend: modelo `DecisionRevisor` unificado; `ColaPanelDecision` (detalle legible + botón de anulación destacado y gateado por capacidad + motivo obligatorio); pantalla React del informe de devolución del alumno, alcanzable desde `MiNota` solo con veredicto de anulación.
4. Rollback: revertir routers al gating por rol y ocultar el endpoint de resolución/informe; los actos append-only del `audit_log` no se borran (cadena de custodia).

### D15 — Gate del write-back a Moodle por estado de revisión (IN-SCOPE, Slice 2)
El write-back de nota a Moodle (`moodle_writeback_estado`, `moodle_writeback.py:71-104`; `estado = pendiente|enviado|fallido`, :99) se **gatea por el estado de revisión de la sesión**:

- Sesión **sin flag** o **resuelta limpia** (`sin_hallazgos` / `aprobado` / `caso_descartado`) → el write-back se **libera y se envía**.
- Sesión **flaggeada / `en_cola_revision` / `caso_abierto`** → el write-back se **RETIENE** (hold), no se envía.
- Sesión resuelta **`anulado_por_fraude`** → **nunca se envía** (queda retenida/invalidada).
- Sesión que estaba en hold y se **resuelve limpia** → se **libera y se envía**.

**Fundamento / orden de ejecución:** el flag se evalúa al **puntuar** (`en_cola_revision = score >= umbral`, `resultados_query.py:410`), al terminar el examen, **ANTES** del envío. Ordenando **puntuar → (si flag) hold**, la sesión problemática nunca llega a `estado = 'enviado'`, de modo que el problema de "ya se escribió en Moodle y no se puede des-escribir" **prácticamente desaparece**. La anulación por fraude, por diseño, cae sobre sesiones que estuvieron flaggeadas → nunca llegaron a `'enviado'`.

**Residual documentado (edge raro):** si por el orden de ejecución real el write-back se disparara **antes** de evaluar el flag, esa sesión quedaría en `'enviado'` y la corrección a Moodle sería **manual** (nunca automatizada — regla dura #5). Con el gate correcto no debería ocurrir. **Al aplicar** hay que **verificar el trigger/timing actual del envío** (¿cuándo pasa `estado` a `'enviado'` respecto de la evaluación del flag?) y asegurar que el hold intercepta antes.

**Alternativa descartada:** enviar siempre y des-escribir al anular → imposible (Moodle no permite des-escribir de forma confiable) y automatizaría la consecuencia académica externa (viola regla #5).

## Decisiones cerradas (antes Open Questions — Slice 2)

Todas las preguntas abiertas del slice 2 fueron **resueltas con el owner** y bajadas a las decisiones de arriba:
- Representación de la "nota" → estado de resolución sobre `proctoring_session`, proyectado a `MiNota`; no se toca Moodle (D10, D11b).
- Canal de notificación → **pull** vía `GET /mis-notas` / `MiNota`, sin infra nueva (D11b).
- Valores canónicos + mapeo del enum → tabla en D6; **`escalada` se dropea** (D6).
- `caso_disciplinario` → **NO se cablea** en slice 2 (D14).
- Evidencia al alumno → informe de devolución con **capturas (URL firmada 15 min) + análisis por señal + decisión + motivo**, SOLO en `anulado_por_fraude` (D12).
