## Why

Hoy un alumno **ve y puede rendir CUALQUIER examen del catálogo sin estar inscripto** a su materia/comisión. Es un agujero de control de acceso, verificado en prod:

- `listar_examenes_contenido` (exam_content/router.py:1266) devuelve **todos** los exámenes del catálogo — *"Cualquier principal autenticado puede consultar el catálogo"* — **sin filtrar por inscripción**.
- El gate `puede_rendir` (inscripcion_service.py:251) es `consentimiento_vigente AND biometria_vigente` — **la inscripción NO participa**. El propio código lo admite: la auto-matrícula *"No altera el gate puede_rendir (solo set-membership)"* (router.py:1309).
- `crear_sesion` (proctoring/sessions) valida ventana + intentos, pero **no** inscripción.

Resultado: la inscripción por código (C-70) es hoy **decorativa** — no restringe nada. La tabla `inscripcion` en prod tiene 0 filas y aun así los alumnos ven el examen demo.

> **Alcance de C-71 (entregado)**: este change agrupó el trabajo que influye en el flujo de examen, en **dos slices**: **(1) gate de inscripción** y **(2) Cola de Revisión + transparencia al alumno**. Ambos entregados, commiteados y archivados.
>
> - **Slice 1 — gate de inscripción: HECHO y commiteado** (commit `cd076f8`). Todo lo de esta sección "What/Capabilities/Impact" de más abajo corresponde al slice 1 y ya está en `main`. Se conserva como registro; no se re-implementa.
> - **Slice 2 — Cola de Revisión + transparencia al alumno: HECHO y commiteado** (`11a21df`). Ver la sección **"Slice 2"** al final.
> - **Sesiones Grabadas — REASIGNADO a C-72.** Contemplado originalmente como "slice 3" de C-71, se movió al change **C-72 `integridad-rendicion-serverside`** para no dejar scope sin entregar en un change archivado. **No formó parte de C-71.**

## What Changes (Slice 1 — HECHO, commit `cd076f8`)

- **La inscripción pasa a ser condición de acceso, no adorno.** El alumno solo ve y solo puede rendir exámenes de las materias/comisiones **donde está inscripto por código**.
- **Materias/comisiones filtradas por inscripción**: la pantalla "Mis materias" muestra **únicamente** las comisiones donde el alumno se matriculó (por código). Sin inscripción → no aparece ninguna materia.
- **Exámenes filtrados por inscripción**: "Exámenes disponibles" muestra solo los exámenes de las comisiones inscriptas. Sin inscripción a esa comisión → el examen **no aparece**.
- **Gate de rendición DOBLE y server-side**: rendir un examen exige **AMBAS** condiciones — (1) perfil completo **Y** (2) inscripto en la materia+comisión de ese examen. Si falta cualquiera, no se habilita. **BREAKING**: hoy alcanza solo con el perfil.
- **Backstop server-side en `crear_sesion`**: además del filtrado del catálogo (frontend), el backend rechaza crear la sesión si el alumno no está inscripto en la comisión del examen (cliente = sensor no confiable, regla dura #6).
- **Nada hardcodeado**: todo sale de la DB real (`inscripcion` por `usuario_id`), no de arrays mock ni catálogos fijos.

## Capabilities (Slice 1 — HECHO)

### New Capabilities
- `enrollment-render-gate`: la inscripción a la materia+comisión es precondición (junto con el perfil completo) para ver y rendir un examen; enforced server-side.

### Modified Capabilities
- `exam-enrollment`: el gate `puedeRendir` deja de exigir solo el perfil y pasa a exigir **perfil completo Y inscripción** a la materia+comisión del examen.

## Impact (Slice 1 — HECHO)

- **Backend (slim = prod)**:
  - `listar_examenes_contenido`: filtrar por las comisiones inscriptas del principal (JOIN con `inscripcion` por `usuario_id`); admin conserva la vista completa.
  - Endpoint/consulta "mis materias/comisiones": derivar de `inscripcion` del alumno (no de todas las comisiones).
  - `puede_rendir` / `InscripcionService`: agregar la condición `inscripto_en(comisión_del_examen)` al gate (además de perfil).
  - `crear_sesion` (proctoring/sessions/router.py): backstop server-side — 403 si el alumno no está inscripto en la comisión del `examen_contenido`.
- **Frontend**: `misMaterias`/`listarExamenesContenido`/`puedeRendir` consumen el resultado ya filtrado; Mis Materias y Mis Exámenes muestran vacío coherente cuando no hay inscripción (CTA a matricularse por código).
- **Datos**: sin migración (usa `inscripcion` existente, C-70). Reusa la FK `examen_contenido.comision_id`.
- **Gobernanza**: control de acceso a exámenes = dominio sensible. Tests sin mocks de DB (regla #4), Pydantic `extra='forbid'` (#5), snake_case (#6), sin hardcodes.

---

# Slice 2 — Cola de Revisión + transparencia al alumno (EN PLANIFICACIÓN)

## Why (Slice 2)

La Cola de Revisión (`frontend/src/screens/proctoring/ColaPanelDecision.tsx`) hoy ofrece 3 decisiones planas (`sin_hallazgos` / `aprobado` / `flaggeado_para_sumario`) y el detalle es poco legible. Tres problemas de fondo:

1. **No hay veredicto ni forma de anular la nota.** El revisor "deriva", pero el sistema no modela el acto de resolver el caso (anular la nota por fraude o descartarlo). El equipo revisor de este deployment **es** la autoridad humana (no hay comité disciplinario separado operando la plataforma), así que necesita poder emitir el veredicto — sin que eso lo vuelva una sanción automática (regla dura de dominio #5 prohíbe la sanción del *sistema/score*, no la decisión de un *humano*).
2. **No hay separación de capacidad.** Revisar evidencia (producir hallazgo) y resolver el caso (anular/descartar la nota) son actos distintos con distinta responsabilidad (KB `03` RACI: revisor deriva; decisión disciplinaria final = Dirección académica). Hoy están fundidos.
3. **El alumno no ve nada.** No puede ejercer el derecho de acceso del titular (Ley 25.326): ver su evidencia, qué dijo cada análisis, la decisión y el motivo.

## What Changes (Slice 2)

- **Modelo de decisión de dos fases (revisar → resolver).** Se separa el acto de **revisar** (producir hallazgo, derivar) del acto de **resolver** (el veredicto sobre la nota). `flaggeado_para_sumario` se **reencuadra** como `caso_abierto` (derivado, sin resolver aún) — NO se funde con la anulación; ver design D6/D7.
- **Nueva resolución `anulado_por_fraude`.** Un acto explícito y separado que **anula la nota**, gateado por el permiso `resolver_caso`. Su contraparte `caso_descartado` cierra el caso validando la nota.
- **Dos permisos de capacidad, no de persona:** `revisar_sesion` (revisar evidencia + hallazgo + derivar) y `resolver_caso` (el veredicto: anular la nota o descartar el caso). **Hoy ambos los tiene el rol revisor** ("desplegar con concentración"); el diseño permite que **mañana** `resolver_caso` se reasigne a otra autoridad (p. ej. Secretaría de Asuntos Estudiantiles / Dirección académica) **solo por config de rol, sin refactor** ("diseñar para separación").
- **Cuatro barandas para anular la nota** (regla #5 humana, #6 server-side, #7 audit): (a) acto separado y explícito; (b) motivo obligatorio + evidencia adjunta, en audit log inmutable; (c) transparencia al alumno; (d) **reversible** (si el alumno apela y tiene razón, la nota vuelve).
- **Motivo obligatorio en CADA decisión** (no solo en la anulación). Hoy `observaciones` es opcional; pasa a requerido y no vacío.
- **Cola mejorada:** drill-down con detalle organizado y legible; botón de anulación destacado y diferenciado del resto; el veredicto solo se muestra/habilita a quien tiene `resolver_caso`.
- **Transparencia al alumno:** pantalla donde el alumno ve su propia evidencia (re-inferida server-side, regla #6), el análisis de cada señal, la decisión del revisor y el motivo. Cada acceso del titular se registra en el audit log (derecho de acceso, Ley 25.326).
- **Enforcement server-side:** el gate `resolver_caso` y la anulación se validan en el backend (backstop, regla #6); ocultar el botón en el front no alcanza.

## Capabilities (Slice 2)

### New Capabilities
- `review-resolution-authority`: el veredicto sobre la nota (anular / descartar) es un acto separado del hallazgo, gateado por la capacidad `resolver_caso` server-side, con motivo + evidencia obligatorios, registrado en audit log inmutable y **reversible por acto compensatorio**.
- `student-evidence-transparency`: el alumno ejerce su derecho de acceso viendo su propia evidencia re-inferida, el análisis por señal, la decisión y el motivo; cada acceso del titular queda auditado. El informe de devolución solo se expone en `anulado_por_fraude` (minimización).
- `moodle-writeback-review-gate`: el envío de la nota a Moodle se gatea por el estado de revisión — hold para sesiones flaggeadas/`caso_abierto`/`anulado_por_fraude`, release para las resueltas limpias; evaluado antes del envío para que la sesión problemática nunca llegue a `'enviado'`.

### Modified Capabilities
- `review-terminal-decision` (spec existente en `openspec/specs/`): evoluciona el modelo de decisión plano a dos fases (revisar/resolver), suma `anulado_por_fraude`/`caso_descartado`, hace el motivo obligatorio, y reconcilia inmutabilidad del registro (RN-RV-06/07) con reversibilidad del efecto (acto compensatorio).

## Impact (Slice 2)

- **Backend**:
  - Nuevo módulo de **capacidades** (capability → roles, config-driven): `revisar_sesion` → {revisor, coordinador, admin_sistema}; `resolver_caso` → {revisor} hoy, remapeable por config. Reemplaza el `require_roles(...)` hardcodeado del router de review por gating por capacidad.
  - `DecisionTerminal` / `ReviewDecisionService` (`backend/app/domain/review/`, `application/review/`): modelo de dos fases; **`escalada` se dropea** (mapeo `descartada→sin_hallazgos`, `derivada→caso_abierto`, `escalada→caso_abierto`); nuevas resoluciones; motivo obligatorio; acto de anulación con evidencia.
  - **Estado de resolución sobre `proctoring_session`** (`anulado_por_fraude`/`caso_descartado`, junto a `decision` de la migración 0013); la nota **no se borra, se invalida** (reversible). La resolución NO muta `moodle_writeback_estado`.
  - **Gate del write-back a Moodle por estado de revisión** (in-scope): solo las sesiones sin flag / resueltas limpias (`sin_hallazgos`/`aprobado`/`caso_descartado`) envían nota a Moodle; flaggeada / `en_cola_revision` / `caso_abierto` / `anulado_por_fraude` → **hold** (no se envía). Puntuar → (si flag) hold, ANTES del envío: la sesión problemática nunca llega a `'enviado'`.
  - Nuevo endpoint de **resolución** (`resolver_caso`) separado del `decide`, y endpoint de **informe de devolución al alumno** gated por `anulado_por_fraude`.
  - **Reversibilidad = acto compensatorio append-only en el `audit_log` existente** (hash-chain + trigger de inmutabilidad Postgres, ya usado por review vía `SqlReviewAuditor`); **cero infra nueva**. El audit distingue revisar / resolver / revertir.
  - **Notificación al alumno = pull**: proyección del veredicto en `MiNota` (`GET /mis-notas`); sin canal push/email.
- **Frontend**: `ColaPanelDecision.tsx` (detalle legible + botón de anulación destacado y gateado por capacidad + motivo obligatorio); tipos `DecisionRevisor` en `lib/types.ts` (modelo unificado, sin `escalada`); nueva pantalla del **informe de devolución** del alumno, alcanzable desde `MiNota` solo con veredicto de anulación.
- **Datos**: migración Alembic (dos pasos) para el estado de resolución sobre `proctoring_session` + mapeo del enum viejo. Sin tabla nueva de actos (usa `audit_log`). **NO cablea `caso_disciplinario`** (existe pero desconectada — fuera de scope).
- **Gobernanza: ALTO/CRÍTICO** (toca notas + disciplina + audit). Reglas: #5 (nunca sanción automática; el humano decide), #6 (server-side, cliente no confiable), #7 (Ley 25.326: minimización + audit del acceso del titular). Código: Pydantic `extra='forbid'`, snake_case, PascalCase en React, tests sin mocks de DB.

## Fronteras explícitas (Slice 2)

- **NO incluye la apelación formal** — es el change aparte **`c-18 verificacion-cadena-apelacion`** (roadmap, 0/20). Slice 2 solo deja el **hook**: la anulación es reversible + notificada al alumno, para que c-18 tenga de dónde agarrarse. No se duplica scope de c-18 (no se construye el flujo de apelación, ni la revisión de cadena de custodia end-to-end).
- **NO incluye Sesiones Grabadas** — reasignado al change **C-72 `integridad-rendicion-serverside`** (ya no es parte de C-71).
