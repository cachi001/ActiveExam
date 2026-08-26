# Tasks — c-78-coherencia-y-mejoras-relevamiento

> Reglas duras del proyecto aplicables a TODA tarea de este change:
> tests contra base real o efímera (**nunca** mock de DB), `extra='forbid'` en todo
> schema Pydantic nuevo, `snake_case` en Python, `PascalCase` en componentes React,
> Conventional Commits **sin** `Co-Authored-By`, no buildear ni commitear sin pedido
> explícito. Gobierno **MEDIO**: implementar por bloques y frenar en los checkpoints
> marcados 🔶 para que el dueño confirme antes de seguir.

## 1. Baja lógica de exámenes — persistencia

- [x] 1.1 Agregar `eliminado_en: Mapped[str | None]` (TIMESTAMPTZ nullable, comentario "NULL = activo, NOT NULL = baja lógica") a `ExamenContenidoModel` en `backend/app/infrastructure/persistence/models/exam_content.py`, copiando la forma del comentario de `UsuarioModel.eliminado_en`.
- [x] 1.2 Crear la migración Alembic `0083_c78_examen_contenido_eliminado_en.py`: `ADD COLUMN` aditiva y nullable, sin backfill; `downgrade` que dropea solo la columna, con nota de que el rollback pierde la marca de baja (los exámenes reaparecen; no se pierde dato de dominio).
- [x] 1.3 Test de migración contra base efímera: aplicar `upgrade`, verificar que los exámenes preexistentes quedan con `eliminado_en` NULL y siguen listándose; aplicar `downgrade` y verificar que no toca ninguna otra tabla.

## 2. Baja lógica de exámenes — API

- [x] 2.1 Agregar `estado: str = "activo"` (`activo` | `inactivo` | `todos`) a `ExamenContenidoSqlRepository.listar_paginado` (`backend/app/infrastructure/persistence/repositories/exam_content.py`), resolviendo el filtro en SQL sobre `eliminado_en` y asegurando que el `total` corresponde al conjunto filtrado.
- [x] 2.2 Exponer el parámetro `estado` en `listar_examenes_contenido` (`backend/app/presentation/api/v1/exam_content/taking_router.py` — recordar que el listado del catálogo vive ahí, no en `catalog_router.py`), con default `activo`. Restringir `estado != "activo"` a principals staff/docente, igual que ya se hace con `materia_id`/`comision_id`.
- [x] 2.3 Implementar `DELETE /{examen_id}` en `catalog_router.py`: gate `gestionar_academico` + `_exigir_pertenencia`, `204`, setea `eliminado_en = now()`, `404` si no existe o ya está de baja. Modelar sobre `eliminar_usuario` en `users/router.py`.
- [x] 2.4 Implementar `POST /{examen_id}/reactivar`: mismo gate, setea `eliminado_en = NULL`, `404` si ya está activo. Modelar sobre `reactivar_usuario`.
- [x] 2.5 Agregar las acciones de auditoría `EXAMEN_BAJA` y `EXAMEN_REACTIVAR` a `backend/app/application/audit/acciones.py` (módulo `EXAMENES`) y registrarlas con `registrar_seguro` en ambos endpoints, siguiendo el patrón de `MATERIA_BAJA`.
- [x] 2.6 Excluir los exámenes dados de baja de `_contar_catalogo` en `backend/app/application/stats/resumen_service.py` (solo el conteo de **inventario**; `_session_conditions` y la actividad NO se tocan — ver design D2).
- [x] 2.7 Tests de API contra base efímera: baja → `204` y desaparece del listado por defecto; segunda baja → `404`; `estado=inactivo` lo devuelve; `estado=todos` devuelve ambos; reactivar → vuelve al listado; reactivar un activo → `404`; sin capacidad → rechazo.
- [x] 2.8 Test de invariante de evidencia: dar de baja un examen con sesiones rendidas y verificar que las sesiones, sus eventos y su evidencia siguen existiendo y son consultables por id, y que `total_sesiones` de Estadísticas NO cambió mientras `total_examenes` bajó en uno.

## 3. Baja lógica de exámenes — pantalla de Exámenes

- [x] 3.1 Agregar `estado` a `listarExamenesContenidoPaginadoFn` en `frontend/src/lib/examContentCatalog.ts` y propagarlo como query param.
- [x] 3.2 Agregar el selector de estado (activo / dado de baja / todos) al `FiltrosPanel` de `frontend/src/screens/ExamList.tsx`, cableado a `query.filters`.
- [x] 3.3 Agregar al `ActionMenu` de cada fila la acción "Dar de baja" (examen activo) o "Reactivar" (dado de baja), con diálogo de confirmación que explique que el examen se oculta del catálogo pero su evidencia se conserva. Recargar la lista tras la operación.
- [x] 3.4 Marcar visualmente las filas dadas de baja cuando el filtro las incluye, para que no se confundan con exámenes vigentes.
- [x] 3.5 Agregar la opción de filtro de auditoría "Baja/reactivación de examen" al catálogo curado de `frontend/src/screens/Auditoria.tsx` (módulo Exámenes), con el patrón `examen.baja,examen.reactivar`.
- [x] 3.6 🔶 **Checkpoint con el dueño**: demostrar el ciclo completo baja → invisible en Exámenes / Dashboard / picker de Notas / conteo de Estadísticas → reactivación, y confirmar que la semántica de la baja es la esperada antes de seguir con el bloque de coherencia.

## 4. Coherencia de denominadores (F-01, F-02)

- [x] 4.1 En `frontend/src/screens/AdminDashboard.tsx`, aplicar el filtro de examen vinculado antes de contar `flagged`, usando el mismo predicado que `enriquecerYFiltrar` (`colaAgregacion.ts`). Extraer ese predicado a una función pura compartida para que exista **un solo** lugar donde vive la definición (design D3).
- [x] 4.2 Reemplazar la `StatCard` hardcodeada de cola del Dashboard por `statProps('enColaRevision', …)`, y hacer que la tarjeta de exámenes también salga del catálogo (agregando la métrica a `STAT_META` si no existe).
- [x] 4.3 Declarar el alcance de cada tarjeta de sesiones en su `sub`: el Dashboard cuenta actividad de cualquier estado; Registro de sesiones cuenta solo finalizadas.
- [x] 4.4 En `backend/app/presentation/api/v1/proctoring/sessions/router.py`, calcular `en_cola_revision` de `/sessions/registro` excluyendo las sesiones sin examen vinculado. **No** cambiar el listado: esa pantalla lista sesiones de diagnóstico a propósito (desde ahí se borran).
- [x] 4.5 Tests unitarios del predicado compartido de "entra a la cola" (sesión con examen y score sobre el umbral, sesión de diagnóstico sobre el umbral, sesión con examen bajo el umbral) y test de API del agregado de `/sessions/registro` contra base efímera.
- [x] 4.6 Test de coherencia cruzada contra base efímera: con un dataset fijo que incluya sesiones de diagnóstico sobre el umbral, verificar que el conteo del Dashboard, el de la Cola de revisión y el `sesiones_en_riesgo` de Estadísticas dan el **mismo** número.

## 5. Filtro de archivadas tri-estado (F-03)

- [x] 5.1 Cambiar `archivado: bool = False` por un parámetro tri-estado (`false` | `true` | `todas`) en `resultados_examen` (`catalog_router.py`), con `422` identificable para valores fuera del conjunto — mismo patrón que la validación ya existente de `estado_entrega`.
- [x] 5.2 Mapear el valor `todas` a `archivado=None` en la llamada a `listar_resultados_examen` (el servicio ya lo soporta: `if archivado is not None`).
- [x] 5.3 En `frontend/src/screens/exam-detail/ResultadosExamenPanel.tsx`, hacer que el checkbox "Mostrar archivadas" mande `todas` (no `true`), conservando `false` como default.
- [x] 5.4 Tests de API: `false` → solo no archivadas; `true` → solo archivadas; `todas` → ambas con `total` correcto; valor inválido → `422`.

## 6. Políticas de intentos por tiempo real (F-04)

- [x] 6.1 Proyectar `creada_en` de la sesión en la fila que consume `_aplicar_politica` (`backend/app/application/moodle/resultados_query.py` y/o el `select` de `sincronizar-moodle`).
- [x] 6.2 Reescribir `_aplicar_politica` en `catalog_router.py` para que `ULTIMO`/`PRIMERO` ordenen por `creada_en` con desempate determinístico por `session_id`. Reemplazar el comentario que justificaba el proxy por uno que explique el criterio real.
- [x] 6.3 Tests contra base efímera con un alumno de dos intentos donde el `session_id` ordena al revés que el tiempo: `ULTIMO` elige el más reciente, `PRIMERO` el más antiguo, `MAS_ALTA` sigue eligiendo por nota y `MANUAL` sigue sin deduplicar.

## 7. Acciones y estados de filtro (F-05, F-06)

- [x] 7.1 En `ExamList.tsx`, corregir la acción "Configurar / vincular" para que navegue al examen de la fila (`/admin/examenes/{id}`) en lugar de a la página genérica de importación; si no existe destino de configuración por examen, retirarla del menú de fila y dejar la importación como acción de pantalla. Documentar cuál de las dos se eligió y por qué.
- [x] 7.2 En `ExamList.tsx`, incluir el filtro de comisión en `hayFiltrosActivos` y en la condición del mensaje de vacío.
- [x] 7.3 En `ResultadosExamenPanel.tsx`, incluir todos los filtros de la pantalla (estado, estado de entrega, archivado, rango de fechas) en la condición del mensaje de vacío.
- [x] 7.4 Alinear el `ActionMenu` de la vista compacta de `ExamList.tsx` con el de escritorio (hoy le falta "Alumnos que rindieron").
- [x] 7.5 Tests de componente de los estados de filtro: aplicar solo comisión habilita limpiar; filtro sin resultados muestra "ningún registro coincide"; base vacía sin filtros muestra "todavía no hay datos".

## 8. Barrido de etiquetas y documentación (F-07)

- [x] 8.1 Remover la clave muerta `pendiente` de `DECISION_META` en `frontend/src/screens/admin/EstadisticasBody.tsx`, verificando primero contra el backend que el único centinela emitido es `sin_revisar`. Conservar el fallback legible para valores desconocidos.
- [x] 8.2 Barrer los `*_META` restantes del frontend de administración (`ACCION_META`, `ETIQUETA_EVENTO`, `MODULO_LABELS`) buscando claves que el backend no emita y valores emitidos sin etiqueta. Corregir solo lo que esté desalineado (design D8: no rebautizar etiquetas que hoy son correctas).
- [x] 8.3 Actualizar los docstrings de RBAC que nombran roles eliminados en c-76: `backend/app/presentation/api/v1/stats/router.py` (cabecera: "docente, admin_examenes"), `taking_router.py` (`listar_examenes_contenido`: "admin/proctor/..."), `catalog_router.py` (comentario de `create_exam_content_router`: "hoy docente, admin_examenes...").
- [x] 8.4 Corregir el docstring de `archivar_resultado` que afirma "mismo scoping por comisión que el resto del panel": es cierto para las escrituras, falso para las lecturas (F-08). Dejarlo describiendo el estado real y referenciando el hallazgo.

---

# Relevamiento del 22/8/2026 (bloques 10 a 16)

> Hallazgos E-01…E-14 del `proposal.md`. Las decisiones cerradas por el dueño están en
> `design.md` D9…D16, y los requisitos en las specs nuevas
> (`visibilidad-resultados-alumno`, `rol-profesor-y-alcance`, `armado-examen-aleatorio`,
> `exportables-academicos`, `lti-registro-dinamico`).
>
> **No se repite acá**: la auditoría con campos crudos (E-13) se solapa con el bloque 8 de
> este mismo change. Lo que c-79 ya arregló (entidad derivada, actor real, link al detalle)
> está hecho; lo que falta lo cubren 8.1 y 8.2.

## 10. Bugs a la vista

- [x] 10.1 **E-12** Completar el registro dinámico LTI: que registrar la herramienta desde Moodle cree la fila con `activo=false` y un admin la habilite. Hoy se carga a mano y se pierde al recrear la base
- [x] 10.2 **E-12** Chequeo de salud que avise si la allowlist LTI quedó vacía, antes de que lo descubra un alumno
- [x] 10.3 **E-12** Pantalla de administración del allowlist LTI (hoy solo existe la API)
- [x] 10.4 **E-13** Separar "cargó y está vacío" de "no pudo cargar" en `MateriasComisiones.tsx`: hoy un 401 se muestra como "No hay materias registradas"
- [x] 10.5 **E-13** `change-password` re-emite el access token cuando cambió el `username`, para que tras el alta LTI la app muestre el usuario elegido y no `lti:1:7`

## 11. Alcance por rol

- [x] 11.1 **E-04** Crear el rol PROFESOR con sus capacidades. NO emite veredicto (eso queda en COORDINADOR); el COORDINADOR conserva exámenes, banco y estadísticas
- [x] 11.2 **E-03** Sacarle al TUTOR el acceso a Estadísticas, Creación de exámenes y Banco de preguntas, en el menú **y** en cada endpoint
- [x] 11.3 **E-05** Filtros de materia, comisión y examen en Supervisión en vivo para coordinador y profesor; el tutor ve solo las suyas
- [x] 11.4 **E-05** Registro de sesiones acotado al tutor, filtrando en la query del backend y no en el frontend

## 12. Configuración por examen

- [x] 12.1 **E-01** Agregar `nunca` a `mostrar_nota` y hacerlo el default de un examen nuevo
- [x] 12.2 **E-01** Botón "Publicar notas ahora" en el detalle del examen, con registro en auditoría de quién publicó y cuándo
- [x] 12.3 **E-01** Bloquear la transición hacia atrás: publicar es camino de ida
- [x] 12.4 **E-02** Opción por examen para mostrar u ocultar los eventos de proctoring al alumno mientras rinde, con default en NO

## 13. Materias, comisiones y exports

- [x] 13.1 **E-11** Colapsar y desplegar cada comisión, en vez de tener todo abierto
- [x] 13.2 **E-11** Paginación del listado de inscriptos (con 40 alumnos hoy es ilegible)
- [x] 13.3 **E-11** Decidir acordeón contra página propia por comisión; de eso depende dónde vive el export
  - **Decidido: acordeón** (lo que ya había). El motivo real del pedido era la ilegibilidad con 40
    alumnos, y eso lo resuelve la paginación de 13.2 sin partir la navegación en dos. Una página
    propia por comisión agregaría una ruta, un breadcrumb y un ida y vuelta para ver algo que se
    consulta junto a las otras comisiones de la materia. El export vive, entonces, en el panel de
    inscriptos del acordeón.
- [x] 13.4 **E-10** Export de alumnos inscriptos por comisión en PDF y Excel, para cruzar contra Moodle
- [x] 13.5 **E-10** Export de notas del examen
- [x] 13.6 **E-10** Marcar el estado de la nota a mano, distinguiéndolo del confirmado por sincronización, con registro de quién lo marcó
- [x] 13.7 **Guarda de "hay gente rindiendo ahora" para materia y comisión** (pedido del dueño)
  - La guarda la tenía **solo el examen**. Dar de baja una materia bloquea la rendición de
    TODOS sus exámenes server-side, así que hacerlo con gente adentro le cortaba el examen a
    medio camino a alguien que no hizo nada mal. Ahora `DELETE /materias/{id}` y
    `DELETE /comisiones/{id}` responden **409** (`materia_en_curso` / `comision_en_curso`)
    con el número de sesiones a las que iban a afectar.
  - **Cambió también el criterio del examen.** "En curso" pasó a ser *sin finalizar Y sin
    vencer*, no *sin finalizar* a secas. Motivo: la auto-finalización es **lazy** (se dispara
    al TOCAR la sesión), así que el alumno que cierra el navegador y no vuelve deja la fila
    abierta para siempre y esa sesión fantasma bloqueaba la baja de forma permanente. El
    vencimiento es el del dominio (`deadline_efectivo`: mínimo entre tiempo límite individual
    y cierre de la ventana). Decisión del dueño: *"la sesión dura por el examen"*.
  - **Hueco conocido**: un examen sin cierre **ni** tiempo límite no tiene vencimiento, y ahí
    la sesión sigue contando como en curso. Sin deadline no hay forma de distinguir una
    sesión viva de una abandonada.
  - `app/application/exam_content/impacto_baja.py` (un solo lugar para las tres entidades) +
    `_rechazar_si_hay_gente_rindiendo` en el router.
- [x] 13.8 **Opción C: avisar cuántas rendiciones tiene antes de confirmar la baja** (pedido del dueño)
  - No cambia ninguna regla: lo ya rendido **se puede** dar de baja y su evidencia se conserva.
    Solo agrega el aviso. `GET .../impacto-baja` para materia, comisión y examen devuelve
    `sesiones_en_curso`, `rendiciones`, `examenes` y `comisiones`; el diálogo de confirmación
    lo pide al abrirse y lo muestra con `AvisoImpactoBaja`. Es una consulta: pedirla no da de
    baja nada, y si falla el diálogo sigue sirviendo (el servidor es igual la autoridad).
  - **"Desactivar materia/comisión" dejó de ser un click directo**: pasa por el mismo diálogo,
    que es donde vive el aviso. Reactivar sigue siendo directo.
  - Dos bugs de coherencia arrastrados que aparecieron al hacerlo: el diálogo de "Eliminar
    materia" seguía diciendo *"esta acción no se puede deshacer"* (es baja lógica reversible
    desde c-78), y la pantalla de Exámenes tapaba el 409 con *"probá de nuevo"*, mandando a
    reintentar algo que reintentar no arregla.
- [x] 13.9 **Un solo patrón de baja: se retiró la "eliminación definitiva"** (pedido del dueño)
  - "Eliminar materia" / "Eliminar comisión" ya **no borraba nada** desde que la baja pasó a
    ser lógica: llamaba al mismo `DELETE` que "Desactivar". Dos entradas de menú con nombres
    distintos para el mismo efecto, y la de "Eliminar" encima solo aparecía si la materia
    estaba VACÍA, que es justo el caso en el que no hay nada que sacar.
  - **Y tapaba un bug**: `onToggleActivaComision` estaba declarado en las props de
    `ComisionesAccordionBody` pero **nunca cableado al menú**. O sea que una comisión con
    inscriptos **no se podía dar de baja desde ninguna parte** — la única entrada que quedaba
    era "Eliminar comisión", que exigía estar vacía.
  - Ahora hay una sola acción por entidad: "Dar de baja la materia/comisión" ↔ "Reactivar".
    Se borró el diálogo de eliminación y su estado (`confirmarBorrado`, `confirmarEliminar`,
    `borrando`).

- [x] 13.10 **Una sola comisión por materia** (decisión del dueño, 26/8/2026)
  - El código de matriculación lo comparte el docente y **no es secreto**: un alumno de C1
    conseguía el de C2 de la misma materia y quedaba en las dos. Verificado que nada lo
    impedía.
  - **Lo que arrastraba**: bajo el modelo replicado (§14.1) cada comisión tiene su propia
    copia del mismo parcial, así que el alumno veía **dos exámenes que son el mismo** y podía
    rendir los dos. Y como las réplicas comparten `moodle_cmid`, las dos notas se escribían en
    el MISMO destino para el mismo alumno: **la segunda pisaba a la primera**.
  - La regla vale en los **tres** caminos, porque si uno solo la puede violar la regla no
    existe: el código del alumno (409 `ya_inscripto_en_la_materia`), el alta manual del admin
    (mismo 409) y la matriculación automática de LTI.
  - **LTI no rechaza el launch**: cortarle el ingreso al alumno por esto sería peor que el
    problema. Simplemente no lo matricula de nuevo y conserva la comisión que ya tenía.
  - Re-usar el código de SU propia comisión sigue siendo idempotente, y otra **materia** no se
    bloquea (un alumno cursa muchas a la vez).
  - `comision_previa_en_la_materia` en el repo (la materia sale de `comision.materia_id`, así
    que el UNIQUE de `inscripcion` no alcanza y hay que preguntarlo con un join).
  - 8 tests contra DB real.
- [x] 13.11 **"Mi perfil" dejaba de mostrar la barra lateral mientras cargaba** (reporte del dueño)
  - Al tocarlo, la barra desaparecía, el "Cargando…" quedaba centrado en toda la pantalla y un
    segundo después volvía todo a su lugar. Ninguna otra pantalla del alumno salta así.
  - La causa: el estado de carga usaba `<StudentShell ocultarNavegacion>` y la vista final
    usa `<StudentShell>` normal, así que la propia pantalla cambiaba de layout entre
    "cargando" y "listo". `ocultarNavegacion` sigue en los pasos del enrollment, que es para
    lo que existe.

## 14. Exámenes

- [x] 14.1 **E-06** Crear un examen para varias comisiones, replicado (N exámenes independientes), en una operación todo o nada
  - **Dato nuevo del dueño que revisa el fundamento de D12**: en el campus hay UNA sola
    aula por materia y las comisiones son **grupos** dentro de esa aula, no cursos
    separados. Cae el argumento "cada réplica apunta al curso de su comisión", pero
    replicar sigue siendo lo correcto: las N réplicas comparten `courseid`/`cmid` y la
    nota se escribe **por alumno**, así que no se pisan. Se midió la alternativa N:M
    (~20 sitios hacen join `examen → comisión` asumiendo cardinalidad 1) y se descartó.
  - Decisiones del dueño: mismo set de preguntas para todas (se sortea una vez y se
    copia), título con el código de comisión entre paréntesis («Parcial 1 (C1)»), y
    selector de comisiones con chips.
  - `comision_ids` en `crear-desde-banco`, migración `0091` con `lote_replica_id`
    (nullable, índice parcial) para saber cuáles nacieron juntas, y aviso en el modal
    ANTES de crear de que quedan independientes.
- [x] 14.2 **E-06** Duplicar un examen, sin arrastrar intentos, resultados ni destino de Moodle
  - `POST /{examen_id}/duplicar`. La copia hereda preguntas (con opciones y blanks) y la
    configuración de mecánica y nota; NO hereda intentos, `notas_publicadas_*`,
    `moodle_courseid/cmid/component` ni `lote_replica_id`. Heredar el `cmid` haría que la
    copia escriba encima de las notas del original.
  - El título de la copia se elige en el diálogo, no después: no existe edición de título
    en el detalle del examen. Default «… (copia)».
  - Acción "Duplicar" en el menú de fila (solo si el examen está vigente) y acción de
    auditoría `examen.duplicar`.
- [x] 14.4 **E-06** Administrar desde el examen qué comisiones lo rinden (decisión del dueño,
  posterior a 14.1/14.2: la comisión no se elige al duplicar)
  - `GET/POST /{examen_id}/comisiones` y `DELETE /{examen_id}/comisiones/{comision_id}`.
    El examen y sus réplicas forman un lote; agregar una comisión crea otra réplica con
    las mismas preguntas y **adopta al original** en el lote (si estaba suelto).
  - **Quitar solo si esa comisión no rindió** (regla del dueño). Con al menos un intento
    devuelve 409 y la UI deshabilita el botón explicando por qué. Tampoco se quita la
    única comisión. Cuando se permite, la réplica sale del lote y queda **dada de baja**
    (recuperable desde "Dados de baja"), no se borra.
  - `_clonar_examen` compartido con 14.2 para que copiar un examen viva en un solo lugar.
  - Sección "Comisiones que rinden este examen" en el detalle del examen + acciones de
    auditoría `examen.comision_agregada` / `examen.comision_quitada`.
- [x] 14.5 Actualizar 5 tests de frontend que quedaron rojos por tareas de c-78 ya marcadas
  `[x]`: `ResultadosExamenPanel` (archivado pasó a tri-estado, §5.3), `ConfiguracionExamenSection`
  (`mostrar_eventos_alumno` en el patch, D10), `Examen` (el panel de integridad gatea los
  eventos, D10) y `ProctoringRevisor` (la llamada a `statProps` quedó multilínea, §4.2).
- [x] 14.3 **deuda c-79** Dropear `comision.docente_id` una vez confirmado que ningún lector la usa
  - **Al ir a confirmarlo apareció un BUG ACTIVO, no una deuda cosmética.** La columna
    quedó *viva pero congelada*: la migración 0086 la backfilleó a `comision_tutor` y la
    dejó en su lugar, pero desde entonces **ningún endpoint la escribe** (el alta de
    comisión no tiene el campo; asignar tutores escribe solo en la tabla puente).
    Verificado con grep: cero escrituras en todo `backend/app`.
  - Sin embargo **dos lectores críticos la seguían consultando**:
    `writeback_service._credencial_para` (con la credencial de QUIÉN se firma la nota que
    va al campus) y `resultados_query` (qué sesiones se marcan `sin_credencial` en Notas).
    Como ese camino **no tiene respaldo institucional a propósito** (C-73 §10.4), toda
    comisión creada o gestionada desde la UI actual devolvía `sin_docente` y **la nota
    nunca salía a Moodle**. En la pantalla de Notas, además, se marcaban TODAS las
    sesiones como sin credencial.
  - **Arreglo**: los dos lectores pasan a `comision_tutor`. Criterio con N tutores, tomado
    del sistema de referencia (su tabla puente tampoco tiene tutor "principal", y su
    autorización es simétrica: cualquier tutor de la comisión puede corregir cualquier
    entrega): **el primer tutor que quedó a cargo y tenga credencial usable**, desempate
    por `tutor_id`. Determinístico a propósito — dos sincronizaciones de la misma nota
    tienen que salir firmadas por la misma persona o la columna *Fuente* de la libreta
    cambiaría sola. Si el primero no conectó su cuenta, se pasa al siguiente; el bloqueo
    solo queda si NINGUNO tiene credencial.
  - Migración `0093` dropea columna e índice. El `downgrade` la recrea y la **reconstruye**
    desde `comision_tutor` (primer tutor por comisión) en vez de dejar todo en NULL.
  - Limpieza asociada: `Comision.docente_id` fuera de la entidad de dominio y del mapeo
    del repositorio; `ExamInfo.docente` fuera del frontend (era siempre `''` y hacía que
    tres pantallas de supervisión renderizaran un separador « · » colgando).
  - Tests: `test_c78_writeback_credencial_nm.py` (5, incluye el caso del bug) +
    `test_c73_credencial_vencida_writeback.py` actualizado a la tabla puente.

## 15. Armado del examen como Moodle (va al final)

> **Decisión de diseño (dueño, 2026-08-25): se sortea contra el POOL COPIADO en el examen,
> no contra el banco vivo.** Verificado contra la documentación de Moodle: Moodle sí se
> protege (versionado de preguntas 4.0+ congela la versión al arrancar el intento; borrar
> una categoría obliga a mover sus preguntas), pero necesita ese versionado **porque
> referencia el banco**, y aun así le queda un agujero documentado: si la categoría se
> queda sin suficientes preguntas al sortear, **el alumno ve un error**. ActiveExam ya
> copia las preguntas al examen (migración 0031, "Opción B / pool"), así que sortear de esa
> copia da la misma protección sin versionar nada y mueve el "no alcanzan" al momento de
> ARMAR. El pool queda congelado; si el banco crece, el examen avisa y el docente decide.
> Una vez que alguien rindió, el pool se bloquea.

- [x] 15.1 **E-07/E-08** Guardar la definición del sorteo en el examen (categoría, subcategorías sí/no, cantidad, etiqueta) en vez de su resultado
  - Migración `0092`: `tramo_sorteo_examen` (categoría, subcategorías, tipos JSONB, cantidad,
    orden) + `examen_contenido.modo_preguntas` ('fijo' | 'sorteo_por_intento', default 'fijo').
  - `crear-desde-banco` con `sorteo_por_intento=true` copia el **pool entero** de cada tramo
    (no las N sorteadas), todo con `seleccionada=False`, y persiste los tramos.
- [x] 15.2 **E-07/E-08** Resolver el set de preguntas por intento, al arrancar cada alumno, y persistirlo en el intento
  - `pregunta_sesion` + `app/application/exam_content/sorteo_por_intento.py`. **Idempotente**
    (recargar devuelve el mismo set: si no, el alumno refrescaría hasta que le toquen fáciles
    y sus respuestas quedarían huérfanas) y con **candado `SELECT ... FOR UPDATE` sobre la
    sesión** — el UNIQUE no alcanza, dos sorteos disjuntos insertarían sin pisarse.
  - `calcular_nota_academica(..., session_id=)`: el **denominador es el set del alumno**, no
    el pool. Sin esto, 10 de 10 bien sobre un pool de 30 daría 3,33. Cableado en los 3 call
    sites (writeback, auto_finalización, sessions/router).
  - `obtener_para_rendir(examen_id, pregunta_ids)` + `proyectar_examen(ya_filtrado=)`: sin
    esto la rendición salía VACÍA en modo sorteo (todo el pool tiene `seleccionada=False`).
- [x] 15.3 **E-07/E-08** Vista previa de la pregunta tal como la ve el alumno, desde el banco y desde el armado
  - `GET /preguntas/{id}/preview` + `PreviewPreguntaModal`. Marca la correcta a propósito: el
    destinatario es el docente revisando SU banco (gate `gestionar_banco`), y el sentido es
    chequear que esté bien marcada. Al alumno no le llega (D3, se filtra server-side).
- [x] 15.4 **E-07/E-08** Desglose en el armado: cuántas hay disponibles por categoría y cuántas se sortean
  - `GET /{examen_id}/sorteo` (por tramo: en el pool contra en el banco) + `SorteoSection`.
    El modal de armado además estima **cuántas preguntas comparten dos alumnos** (largo²/pool),
    que es la cuenta que decide si el sorteo sirve de algo.
  - `POST /{examen_id}/sorteo/actualizar-pool` incorpora las nuevas del banco; 409 si el
    examen ya tiene intentos.
- [x] 15.5 **E-07/E-08** Permitir mezclar tramos fijos y aleatorios en un mismo examen
  - Sale del modelo: las `seleccionada=True` van primero y no participan del sorteo, después
    van los tramos. "3 fijas + 4 de Unidad 1" es un examen válido.
- [x] 15.6 **E-09** Validar el tope de preguntas contra las realmente disponibles, en el backend
  - El 422 `sorteo_insuficiente` ya existía al armar; se le suma que el tope
    `limite_preguntas` se compara contra la **suma de los tramos** (lo que rinde el alumno) y
    no contra el pool, que es a propósito más grande. `PoolInsuficienteError` es la red de
    seguridad en la rendición (409), no el camino esperado.

## 15bis. Examen en borrador (E-07, pedido del dueño)

> No había forma de probar un examen sin exponerlo: la ventana apertura/cierre es obligatoria
> y se aplicaba igual al docente, así que adelantar la apertura para esconderlo también lo
> dejaba afuera a él.

- [x] 15b.1 `examen_contenido.borrador` (migración 0092) + `ExamenEnBorradorError` (403) en el
  enforcement. Backstop server-side, igual que la baja lógica: sacarlo del listado no alcanza
  contra una URL guardada.
- [x] 15b.2 `es_prueba_de_staff` derivado del **rol** (no de un flag del body — regla dura #6):
  saltea borrador Y ventana (probar tiene sentido ANTES de la apertura), pero NO la baja
  lógica ni el tope de intentos.
- [x] 15b.3 `POST /{examen_id}/habilitar` (de ida) + `BorradorSection` + chip "Sin habilitar"
  en el listado + `incluir_borradores=False` en la vista del alumno.

## 16. Capacidad y rendimiento

- [x] 16.1 **E-14** Correr la medición de carga contra el sistema real y escribir los resultados (hardware, punto de quiebre, configuración)
  - Medido el 25/8/2026 contra la instancia real de Render (plan free). Techo de
    transporte **80 req/s**; a 100 concurrentes satura (p50 de 280 a 875 ms) pero **no
    falla**: cero errores. El tráfico dominante NO son las capturas sino el **chat** (tres
    pollers por alumno: chat 3,5 s, pausas 3,5 s, grilla 4 s = ~82 req/s con 100 alumnos).
    CPU no es el cuello: la re-inferencia MediaPipe cuesta 20 ms por captura, ~3% del core
    con 100 alumnos. **El cuello era el disco**: un examen de 100 alumnos escribía 2565 MB
    de capturas en una base de 1024 MB. Cuatro decisiones aplicadas (cámara a 960×540,
    heartbeat a 180 s, chat apagado por defecto, retención configurable de 180 días con
    mínimo 90) lo bajaron a **443 MB**. Detalle en engram: `activeexam/capacidad-render-free-medida`.
- [x] 16.1b **E-14** Simular la **caída de conexión** de un alumno durante el examen
  - `CAIDA_SEG` / `CAIDA_PCT` / `CAIDA_EN_SEG` en el harness. Lo que se mide NO es que
    aguante menos tráfico (mientras está caído no manda nada) sino el **regreso**: el cliente
    bufferea en IndexedDB y drena todo junto, y si se cae el wifi del aula vuelven todos a la
    vez. Por eso la caída arranca a la misma altura de la iteración en todos los VUs.
  - **Medido (26/8/2026, stack local, 70 alumnos caídos 30 s a la vez): CERO evidencia
    perdida, cero errores.** Drenaje de 1,08 s de media para la ráfaga de vuelta.
  - La verificación necesita token de **admin**, no de coordinador: el detalle de la sesión es
    de supervisión y desde c-79 el coordinador está acotado a SUS materias, así que con
    sesiones `modo: 'test'` (sin examen vinculado) la pertenencia no resuelve y da 403 igual
    que el alumno. La primera corrida marcó 100% de evidencia perdida por ese 403 y no por
    una pérdida real.
- [x] 16.1c **E-14** Simular la **avalancha LTI** de 70 a 100 altas — encontró un bug grave
  - `tools/carga/avalancha-lti.py`. Registra una plataforma falsa en
    `lti_deployment_confiable` apuntando al JWKS que sirve el propio script (el `jwks_uri` se
    guarda por deployment, así que no se toca ninguna plataforma real) y la borra al terminar.
  - **H-07 (CRÍTICO, corregido) — el mismo bug que bcrypt, en otro lado.**
    `_default_jwks_fetcher` usa `httpx.get`, que es SINCRÓNICO, y se llamaba derecho dentro
    de la corrutina del launch. Sin cache: **una bajada por launch**. Medido con 70 alumnos
    entrando a la vez: 10,9 s la avalancha, **8 s de mediana por alumno**, 70 pedidos al
    JWKS, y el canario (que mide cómo responde el servidor para TODO lo demás, incluidos los
    que ya están rindiendo) saltó de 8 ms a **4075 ms**.
  - Arreglo en dos mitades, porque el cache solo no alcanza: `JwksPlatformCache` cachea por
    `jwks_uri` con TTL **y** manda la bajada a un hilo (el primer alumno del día siempre
    encuentra el cache frío). Single-flight para que 70 llegadas simultáneas con el cache
    frío no sean 70 bajadas contra un campus que también está saturado. Y un `kid` ausente
    fuerza UN refresco, que es el riesgo que introduce cachear: si el campus rota sus claves,
    el JWKS viejo dejaría fallar todos los launches hasta que venza el TTL.
  - **Después del arreglo: 4,1 s la avalancha (era 10,9), 2809 ms por alumno (era 8039),
    4 pedidos al JWKS (era 70 — son 4 porque uvicorn corre con 4 workers y el cache es por
    proceso), canario 1582 ms (era 4075).**
- [x] 16.1d **E-14** **H-08 (corregido)** El alta por LTI hasheaba una contraseña que nadie iba a usar
  - El alta JIT generaba una contraseña **aleatoria de 32 bytes** y la hasheaba con bcrypt
    (248 ms) solo para llenar la columna. Esa contraseña **nunca se le comunica a nadie**: el
    alumno entra por LTI, y si quiere entrar directo fija la suya desde el dashboard
    (`debe_cambiar_password=True`; el primer set de un usuario LTI ni siquiera pide la
    anterior, ver `auth/router.py::lti_primer_set`). 248 ms por alumno para hashear un
    secreto que nadie iba a verificar nunca.
  - En su lugar, un **centinela** `HASH_SIN_PASSWORD = "!sin-password"`. Arranca con `!`
    porque bcrypt siempre produce hashes que empiezan con `$2`: ningún texto plano puede
    hashear a eso. Mismo patrón de "unusable password" de Django.
  - `verificar_password` falla **cerrado** ante el centinela, la columna vacía o basura, y
    **gasta igual el tiempo** de una verificación real (`verificar_password_dummy`): devolver
    `False` al instante delataría por tiempo qué cuentas todavía no fijaron contraseña, que
    es el mismo agujero de enumeración que ya se había tapado en el login.
  - **Medido, misma avalancha de 70 alumnos: 1,5 s (era 4,1 tras el arreglo del JWKS y 10,9
    al principio) · 1261 ms por alumno (era 2809 y 8039) · canario 311 ms (era 1582 y 4075).**
    O sea: **la avalancha pasó de 10,9 s a 1,5 s y la degradación del resto del sistema de
    4075 ms a 311 ms.**
  - Red de seguridad de auth verde: `test_c55_hashing` 4, `test_c75_lti_password_setup` 4,
    `test_c76_18_change_password_jwt_provider` 5, `test_password_policy` 9, `test_c75_lti_jit`
    16, `test_c55_login_endpoint` 1. Más `test_c78_lti_sin_password.py` (7, nuevo).
- [x] 16.1e **E-14** Correr todo contra **Render**, no solo local (26/8/2026, ya mergeado a main)
  - **Carga 70 alumnos / 3 min**: cero errores, 4024/4024 checks, pero **19 req/s** contra 47
    local. Evento med 3,1 s · **p95 7,8 s**. Crear sesión med 3,89 s · p95 9,55 s. **No es la
    red**: TLS 70 ms medido, y en reposo un endpoint trivial responde en 320 ms. Es la CPU del
    plan free.
  - **Caída de conexión, 70 alumnos caídos 30 s**: **cero evidencia perdida**, igual que
    local. PERO el drenaje del buffer tarda **med 35,6 s · max 1m01s** (local: 1,08 s).
    ⚠️ **Riesgo abierto**: si el alumno cierra la pestaña durante esos 35 s, esa evidencia se
    va con él. Se arregla mandando el buffer en lote en vez de un evento por request.
  - **Avalancha LTI, 70 alumnos**: 70/70 entran. 10,8 s la avalancha, 9387 ms por alumno,
    **1 solo pedido al JWKS** (el cache funciona). El canario va de 212 ms a 3701 ms mientras
    entran: degradación real pero acotada a esos ~11 s, y nada falla.
  - **H-09 (CRÍTICO, corregido) — el sello del cache de JWKS.** La guarda anti-amplificación
    que introdujo H-07 era un **flag permanente**: tras el PRIMER refresco por un `kid`
    faltante, el cache quedaba sellado y no volvía a refrescar por ningún kid nuevo hasta
    vencer el TTL. O sea: un campus que rota sus claves **dos veces** deja TODOS sus launches
    fallando con `kid_desconocido` **durante una hora**. Pasa a ser un cooldown de 10 s.
    Solo se veía contra producción y con corridas repetidas — local, cada reinicio del
    backend limpiaba el cache.
  - **Nota sobre qué mide la avalancha**: un launch de cuenta NUEVA no persiste el usuario,
    crea una confirmación pendiente y redirige a `/lti-confirmar` (gate del bug de
    2026-08-19). Igual ejercita el costo del alta completa, porque `identidad_es_nueva` corre
    `provisionar_o_recuperar_usuario` dentro de un SAVEPOINT y lo deshace. Verificado que
    producción quedó limpia: 9 usuarios, ninguno de la avalancha, y ninguna plataforma falsa
    en la allowlist.
  - Para correrlo contra Render el script suma `--via-api` (registra la plataforma falsa por
    la API admin, sin acceso a la base) y `--jwks-publico` (Render tiene que poder alcanzar
    el JWKS; se expuso con un túnel temporal, ya cerrado).
- [x] 16.1f **E-14** Mandar el buffer de eventos **en lote** al reconectar
  - `POST /sessions/{id}/events/lote` acepta la tanda entera en un request, **en orden**, y
    devuelve un ack por evento en la misma posición. Es el **mismo**
    `event_service.ingestar_evento` que la ingesta de a uno, no una copia: misma
    re-inferencia, misma guarda de pertenencia (H1, IDOR) y mismo contrato de ack. Tope duro
    de 200 por lote.
  - `drainAndReplayEnLote` mantiene las garantías del replay: orden de producción, purga
    **solo lo confirmado y por id** (nunca por posición a ciegas — si el backend devolviera
    menos acks, lo que no vino sigue en el buffer), y una tanda que falla no se da por
    enviada ni se lleva puesta la anterior. Si el lote falla cae al camino de a uno; el
    backend deduplica por `event_id`, así que reintentar no duplica.
  - 7 tests de backend (DB real) + 8 de frontend.
- [x] 16.1g **E-14** Correr la carga de **100 alumnos** contra Render
  - **Aparece el primer fallo**: 1 request de 4192 (0,02%, un poll de chat). Con 70 eran cero.
  - Evento med 3,7 s · **p95 12,67 s** · max 29,4 s. Crear sesión med 4,85 s · p95 16,34 s.
  - **El techo está en ~19 a 20 req/s y no se mueve**: con 70 alumnos daba 19,0 req/s y con
    100 da 19,7. Sumar alumnos ya no agrega trabajo hecho, solo agrega espera. Eso es
    saturación, no una curva que todavía sube.
  - Cero evidencia perdida, cero errores de ingesta.
- [ ] 16.2 **E-14** Dimensionar el arranque de producción con los cores del plan una vez que deje de ser free, recalculando el pool (`workers × 24` conexiones contra `max_connections`)
  - Diferido por decisión del dueño: el plan sigue siendo el free y la VPS se evalúa después.
- [x] 16.3a **E-14** Proteger `/metrics`, que estaba **público sin autenticación** en producción
  - `app/observability/metrics_auth.py`, política única para los dos main. Sin
    `METRICS_TOKEN` el endpoint **no existe** (404, fail closed: olvidarse la variable en un
    entorno nuevo no puede volver a abrirlo); con la variable exige
    `Authorization: Bearer`, que es el esquema que Prometheus habla nativo. Comparación con
    `compare_digest` y lectura de la variable en cada request (rotar el token es reiniciar,
    no reconstruir la app). El middleware sigue contando aunque el scrape esté cerrado.
    6 tests en `test_c78_metrics_protegido.py` + 2 en `test_app_factory.py`.
    Cableado en `docker-compose.dev.yml` + `prometheus.dev.yml`.
- [ ] 16.3b **E-14** Que algo scrapee y guarde `/metrics` en producción, con retención que cubra el examen
  - Bloqueado por una decisión del dueño: hoy no hay dónde guardarlo (Render free no corre
    un Prometheus al lado). Opciones a resolver: Grafana Cloud free, un scraper propio, o
    aceptar mirar `/metrics` a mano durante el examen.
- [x] 16.4 Sacar los screenshots de base64 en Postgres
  - **La cifra de la task estaba corta.** Medido con `pg_column_size` contra Postgres real,
    una captura de 85 KB ocupaba **151.224 bytes**, no ~113 KB: es una expansión base64
    DOBLE (el data URL, y encima el token Fernet, que también es base64). Y TOAST no la
    salva: lo cifrado es incompresible y Postgres lo guarda tal cual.
  - Guardando el token Fernet **crudo** sobre los bytes de la imagen, la misma captura ocupa
    **85.065 bytes**: **44% menos**. Un examen de 100 alumnos pasa de **577 MB a 325 MB** en
    una base de 1024 MB.
  - Migración **0097** (aditiva, dos pasos): `screenshot_bin` (BYTEA) + `screenshot_prefijo`.
    `screenshot_b64` se conserva con el histórico; el DROP va en una migración posterior.
  - **Ningún hash cambia.** El prefijo del data URL se guarda **tal cual vino** (no un mime
    normalizado), así que el string se reconstruye byte a byte y `screenshot_sha256` sigue
    verificando. Fijado por tests de round-trip exacto.
  - `leer_captura()` es el ÚNICO camino de lectura: resuelve columna nueva vs. legacy y
    descifra. Lo usan el detalle del revisor y verify-chain; ninguna pantalla lo resuelve
    por su cuenta.
  - La purga de retención borra **las dos** columnas. Borrar solo la vieja habría dejado de
    purgar de verdad justo cuando la captura pesa más (Ley 25.326).
  - 16 tests nuevos (8 puros de round-trip + 8 e2e con Postgres real).
- [ ] 16.5 Mandar la captura binaria en vez de base64, que ahorra un tercio del tráfico
  - **No se hizo, a propósito.** El terreno quedó preparado: con `separar_data_url` /
    `reconstruir_data_url` el cliente puede mandar `(prefijo, bytes)` y el servidor
    reconstruye el string exacto para hashear, así que **tampoco cambiaría ningún hash**.
  - Lo que falta es contrato de red nuevo (multipart) + que el buffer del cliente guarde
    Blobs en vez de base64. Es tocar la ruta crítica del examen una vez más, y el beneficio
    (~25% menos de subida) es el más chico de la lista: la medición del 25/8 mostró que el
    tráfico dominante es el **chat**, no las capturas. Con el examen real encima, va después
    de que el dueño pruebe lo que ya está.
- [ ] 16.6 Reemplazar el polling de 4 a 6 s por SSE (change c-15b), que baja a cero el costo de los paneles inactivos
  - **Diferido a propósito, no olvidado.** Analizado con el dueño: SSE **no hace que el alumno
    rinda mejor** — contestar, autoguardar, la cámara y la detección no pasan por el polling.
    Lo que mejora es la latencia de la pausa (~4 s → instantáneo), la supervisión del tutor, y
    el techo de req/s. Con 16.12 abajo ya se sale de la saturación, así que el aporte marginal
    para 100 alumnos es chico frente al riesgo de cambiar el transporte del examen en vivo a
    una semana de la fecha. Va después del examen.
  - **SSE y no WebSocket**: el tráfico es de UNA dirección (el servidor avisa; lo que manda el
    alumno son POST normales que ya andan) y `EventSource` **se reconecta solo** por
    especificación del navegador. Un WebSocket caído en silencio deja al alumno sin
    aprobaciones de pausa y nadie se entera.
  - **El bloqueo de la regla dura #4 ya casi no aplica**: lo que C-03 tenía que decidir era el
    *backplane* de fan-out entre instancias. Producción corre **un solo proceso** de uvicorn
    (sin `--workers`, verificado en `Dockerfile.activeexam`), así que no hay nada que
    compartir: un pub/sub en memoria alcanza.
- [x] 16.12 Cadencia adaptativa del poller de pausas — el cuello de botella real
  - **Medido en el código**: el techo es 80 req/s y lo consume el **polling por alumno**, no
    las capturas. `PausaAlumno` preguntaba cada 3,5 s durante las 2 h del examen por algo que
    casi nunca pasa: **~29 req/s permanentes** con 100 alumnos. Y cuando el techo satura no se
    pone lento el chat, se pone lento **todo**, incluido el autoguardado de las respuestas
    (p50 de 280 ms a 875 ms). El poller de la pausa le competía el ancho de banda al guardado
    del examen.
  - **Se puede ir lento sin que el alumno espere más** porque la pausa **siempre la inicia
    él** (`solicitar_pausa` es el único endpoint de creación; el tutor solo aprueba o
    rechaza). Mientras no pidió nada, no puede llegarle nada que no haya pedido. Al tocar el
    botón, `setPausa()` con la respuesta del POST hace que el intervalo vuelva a 3,5 s **en el
    mismo render**: la espera percibida es idéntica.
  - 20 s en reposo → el poller baja de ~29 a ~5 req/s. Total **82 → ~59 req/s**: sale de la
    saturación sin tocar el transporte.
  - **NO se le aplica al chat**: ahí el que inicia es el TUTOR (el alumno no puede abrir el
    hilo, solo responder), así que bajarle la frecuencia le haría llegar el mensaje 20 s tarde.
  - `screens/pausaCadencia.ts` (función pura) + `PausaAlumno.tsx`. 7 tests.
- [x] 16.7 Que la evidencia sobreviva a un corte de conexión. Condición del dueño: "no se pueden perder capturas y eventos"
  - **Corrección del diagnóstico previo**: las capturas de incidente SÍ estaban
    protegidas — el `screenshot_base64` viaja dentro del payload que se bufferea. La que
    salía sin respaldo era la `captura_pausa`. Pero el buffer tenía tres defectos que con
    capturas adentro lo volvían inservible, y aparecieron dos rutas de pérdida silenciosa:
  - **H-07 (CRÍTICO, corregido)** — el id de evento (`evt-1`, `evt-2`…) reiniciaba el
    contador en cada montaje del `VisionPipeline`. Un alumno que recargaba con eventos sin
    enviar generaba un `evt-1` que **colisionaba** con el `evt-1` viejo todavía en cola: el
    buffer lo tomaba por duplicado y no guardaba el nuevo, y al confirmar el POST **purgaba
    el viejo, que nunca se había enviado**. Ahora el id lleva prefijo único por instancia.
  - **H-08 (CRÍTICO, corregido)** — `replaySender` devolvía `persisted` sin mandar nada
    cuando todavía no había sesión, y `drainAndReplay` purga con cualquier ack: un drenaje
    disparado antes de que la sesión existiera **borraba el buffer entero sin enviarlo**.
    Ahora falla, y el reintento lo reintenta cuando la sesión está.
  - **H-09 (corregido)** — el drenaje colgaba solo de `window.'online'`. Si la conexión
    volvía sin que el navegador disparara el evento, o si el alumno **recargaba la página**
    después del corte (lo que hace cualquiera), lo bufferizado no se reenviaba nunca.
    `crearReintentoDeDrenaje` drena al arrancar y cada 30 s, sin depender del navegador.
  - **Tope por peso** (`DEFAULT_BUFFER_MAX_BYTES` = 200 MB) en vez de por cantidad: 10.000
    registros de 114 KB eran 1,1 GB, más de lo que ningún navegador concede. El calibre sale
    del peor caso real del motor de reglas (~1.200 capturas/hora ≈ 137 MB si alguien se tapa
    y destapa la cara sin parar; un examen normal no llega a 1 MB), justamente para que el
    buffer **no se llene** y no haya que elegir qué evidencia se tira.
  - **`append` dejó de leer el buffer entero en cada evento**: peso total y `seq` se calculan
    una vez al arrancar y se mantienen incrementales. Antes, guardar el evento 50 significaba
    parsear 5,7 MB de base64 en el hilo principal, encima del examen del alumno.
  - **`nextSeq` continúa desde el mayor `seq` guardado**: antes volvía a cero tras un reload y
    los eventos nuevos se numeraban por debajo de los que esperaban, así que el replay los
    reenviaba desordenados.
  - **Nada se descarta en silencio**: expulsar por presupuesto o que el navegador niegue el
    guardado avisa por `alAvisar`, y `Examen.tsx` lo muestra (`pendiente` se recupera solo;
    `perdida` no se limpia nunca).
  - Archivos: `transport/eventBuffer.ts`, `transport/envioConRespaldo.ts` (nuevo),
    `transport/indexedDbBufferStore.ts`, `proctoring/visionPipeline.ts`,
    `proctoring/useExamProctoring.ts`, `screens/Examen.tsx`. 16 tests nuevos.

- [x] 16.8 **LA CAUSA RAÍZ**: la capa de API mentía sobre si los envíos llegaban, y eso dejaba
  muerto TODO el manejo de error construido encima
  - **H-10 (CRÍTICO, corregido)** — `enviarEventoProctoring` hacía `catch { return null }`.
    El patrón buffer-first del examen es `append → POST → confirm(purgar)`, y como el POST
    **nunca rechazaba**, el `confirm` corría SIEMPRE, incluso con la red caída: **el buffer
    de IndexedDB se vaciaba solo en cada evento y el replay no encontraba nunca nada que
    reenviar.** Toda la resiliencia ante cortes —incluida la de 16.7— era decorativa hasta
    acá.
  - **H-11 (CRÍTICO, corregido)** — `enviarRespuestasProctoring` degradaba a `null` todo lo
    que no fuera un 409 de plazo. Eso dejaba muerto el manejo de error de los dos llamadores
    de `Examen.tsx`, que estaban escritos bien: (a) la rama de `entregar()` que dice
    "error de red en entrega manual: revertir para permitir reintento, **no finalizamos**"
    —con el comentario "terminarle el examen sin haber guardado nada sería el peor resultado
    posible"— **nunca corría**, y el examen se finalizaba igual con las respuestas sin llegar
    al servidor; (b) el aviso `guardadoEnRiesgo` se **apagaba** justo cuando había que
    encenderlo, porque el POST resolvía con `null` en vez de rechazar.
  - **H-12 (corregido)** — `enviarBiometriaProctoring` devolvía **`{ ok: true }`** con la red
    caída: afirmaba éxito. El llamador borraba el payload de la verificación de identidad
    dándolo por entregado, y esa verificación no volvía nunca.
  - **H-13 (corregido)** — el payload biométrico pendiente se limpiaba del store en la misma
    línea del POST, sin esperar el resultado. Un hipo de red al arrancar el examen —el
    momento en que entran todos a la vez— lo borraba para siempre. Ahora se suelta solo
    cuando el backend contestó, y el mismo reintento que drena el buffer lo reenvía
    (`crearEnvioReintentable`).
  - **H-14 (corregido)** — `obtenerRespuestasProctoring` devolvía `[]` ante un fallo de red.
    Es la restauración al reanudar: el alumno que recargaba veía un examen **en blanco**
    aunque el servidor tuviera sus respuestas. Ahora propaga, se reintenta 3 veces y, si no
    sale, se le avisa que lo suyo está guardado y que no vuelva a cargarlo.
  - **H-15 (corregido)** — `finalizarSesionProctoring` se tragaba el error: una sesión que no
    se finalizaba quedaba "en vivo" para siempre en el panel del proctor.
  - Archivos: `lib/apiProctoring/sesion.ts`, `lib/apiProctoring/respuestas.ts`,
    `screens/Examen.tsx`, `screens/Biometria.tsx`, `screens/harness/sinkEventHandler.ts`,
    `transport/envioConRespaldo.ts`. 23 tests nuevos.

- [x] 16.9 Cadena de custodia cliente → backend del screenshot (regla dura #6)
  - **H-16 (corregido)** — `screenshot_sha256_cliente` se aceptaba en el schema desde C-64 y
    el servicio lo **descartaba**, con un comentario explícito de que no había columna. La
    primera capa de la cadena de custodia no existía: nadie comparaba nada.
  - Y los dos lados hasheaban **cosas distintas**: el cliente hashea los bytes decodificados
    de la imagen y `sha256_hex` hashea los bytes UTF-8 del string base64 completo, prefijo
    `data:image/jpeg;base64,` incluido. Compararlos de frente habría marcado **todos** los
    eventos como manipulados. Se agregó `sha256_de_imagen`, que hashea lo mismo que el cliente.
  - Migración **0096**: `proctoring_event.screenshot_sha256_cliente` + `custodia_cliente`
    (`coincide` | `discrepancia` | `no_verificable`). Verificada upgrade + downgrade +
    re-upgrade en base limpia. Las filas viejas quedan en `no_verificable`, que es la verdad.
  - L2.5 (regla dura #5): una discrepancia **nunca** rechaza el evento ni sanciona. Se asienta
    y se loguea (los hashes, nunca la imagen) como señal para el revisor humano.
  - 14 tests nuevos (10 puros + 4 con Postgres real).

- [x] 16.10 Arreglar lo que estaba roto en el entorno y en el harness de tests
  - **H-17 (CRÍTICO, corregido)** — `verify-chain` comparaba el hash del **texto plano**
    contra el hash del **cifrado**. `screenshot_sha256` se calcula antes de cifrar y
    `SqlEventMaterialRepository` leía la columna tal cual (el token Fernet). Con el cifrado
    activo —y lo está— daba `broken`, o sea **evidencia manipulada, en todos los eventos**.
    Y no es un endpoint de perito: `informe_service` corre ese mismo servicio sobre **cada
    captura del informe de devolución que ve el alumno**. Le estábamos diciendo a cada
    alumno que su propia evidencia estaba adulterada. El repo ahora descifra; el cipher se
    cablea desde `app.state` en los dos llamadores. El test de integración que ya existía no
    lo agarraba porque escribía la captura **en claro**: probaba un escenario que en
    producción no ocurre.
  - **H-18 (corregido)** — `scripts/seed_users.py` seguía escribiendo `comision.docente_id`,
    columna que la migración 0093 dropeó. El seed **reventaba a la mitad**: un
    `docker compose up` limpio dejaba la base sin tutor asignado y sin matriculaciones.
  - **H-19 (corregido)** — `docker-compose.dev.yml` seteaba `ENVIRONMENT: development`, que
    no es uno de los cuatro valores que acepta `Settings.environment`. Cualquier código que
    construyera `Settings` reventaba con `ValidationError`; hoy solo se notaba en los tests
    porque `main_activeexam` no usa `Settings`.
  - **H-20 (corregido)** — los 4 tests rojos de `useUiPrefs` que se habían dado por "ajenos
    al proyecto" (H-06: "jsdom 25 no expone localStorage bajo Node 26") **no eran ajenos**:
    Node 22+ define su propio `localStorage` global (undefined sin `--localstorage-file`) y
    **pisa** al de jsdom. Se repara en `src/test/setupStorage.ts` para toda la suite, sin
    tocar versiones. **Frontend quedó en 1012/1012.**
  - **H-21 (corregido)** — la base de test se arma desde el modelo ORM, sin migraciones, así
    que nunca tenía el singleton de `configuracion_sistema` que siembra la migración 0014.
    Sin esa fila, arrancar una sesión de proctoring responde **503 `config_no_disponible`**,
    y eso tumbaba en bloque a todos los módulos que crean una sesión — por una carencia del
    harness, no por un defecto del código. Producción no estaba afectada (ahí la fila la
    crea la migración).
  - **H-22 (corregido)** — el fixture `autouse` del conftest raíz recorría **las ~45 tablas
    una por una, cada una en su transacción**, para cada uno de los 264 módulos: **3,1 s de
    setup por módulo**, hasta en módulos que no tocan la base. Ahora resuelve con **una**
    consulta a `pg_tables`: **0,80 s**. Misma semántica, sigue creando solo lo que falta.

- [x] 16.11 **La configuración del sistema tiene que valer en todos lados** (pedido del dueño)
  - **H-23 (CRÍTICO, corregido)** — `chat_habilitado` y `pausas_habilitadas` eran **solo
    visuales**: `Examen.tsx` escondía el recuadro y **ninguno de los 7 endpoints** de
    `chat_pausa/router.py` consultaba la config (verificado con grep: cero referencias).
    Apagarlos **no apagaba nada**: cualquier cliente seguía escribiendo y polleando. Rompía
    la regla dura #6 (la regla la hace valer el backend) y hacía que la decisión de
    capacidad "chat apagado por defecto" **no tuviera efecto real** sobre la carga — o sea
    que el alivio que se le atribuyó en 16.1 no existía.
  - **El gate lee del SNAPSHOT, no de la config viva.** Decisión del dueño: la config no se
    refresca a mitad del examen, para eso existe `config_snapshot`. Si el gate mirara la
    config viva, un cambio a mitad de una rendición la alteraría — exactamente lo que el
    snapshot existe para impedir. El snapshot ahora congela también los dos interruptores;
    las sesiones viejas sin ese dato caen a la config viva, igual que el resto de sus lectores.
  - **NO se cierra la finalización de una pausa ya activa**: apagar el interruptor no puede
    dejar a un alumno pausado para siempre.
  - **H-24 (corregido)** — el default `true` le ganaba a la base en **tres** lugares
    (`ConfigEfectiva`, el fallback `?? true` del cache del front, y `useState(true)` de
    `Examen.tsx`), pese a que la migración 0095 ya lo había puesto en `false`. El último era
    además el peor para capacidad: **todos los alumnos polleaban el chat hasta que llegaba la
    config**, justo en el arranque del examen. Las pausas quedan en `true` a propósito:
    negarle una pausa a alguien por un dato que no llegó es peor que el costo de tenerlas.
  - **H-25 (corregido)** — salió a la luz acá: `tiene_pertenencia_de_sesion` compara contra
    columnas UUID y un `subject` malformado hacía **reventar el cast de asyncpg con un 500
    donde correspondía un 403**. Ya había pasado por otro camino (guarda `_es_uuid` de
    `stats/resumen_service`); este había quedado sin cubrir.
  - **H-26 (corregido)** — `test_chat_api.py` estaba **roto desde c-79** (4 de 9 en rojo, con
    500 de asyncpg) y nadie lo había notado: usaba `coordinador` con el comentario "tiene
    alcance institucional, sin restricción de pertenencia", supuesto que **c-79 invalidó** al
    acotar al coordinador a su materia. Verificado con `git stash` que fallaba idéntico sin
    mis cambios. Actualizado a `admin_sistema` (el único institucional que queda).
  - 22 tests verdes: 7 puros + 6 HTTP nuevos + los 9 de `test_chat_api` recuperados.

## 17. Cierre

- [x] 17.1 Verificar que `openspec validate` pasa para el change y que cada requisito de las specs tiene al menos un test que lo ejercita.
  - `openspec validate --changes` pasa (4/4). Corregidas 5 specs nuevas que usaban el
    formato de spec completa (`## Requirements`) en vez de delta (`## ADDED Requirements`)
    y por eso el change entero no validaba: `armado-examen-aleatorio`,
    `exportables-academicos`, `lti-registro-dinamico`, `rol-profesor-y-alcance`,
    `visibilidad-resultados-alumno`.
- [x] 17.2 Redactar el registro de hallazgos final: F-01…F-07 con su estado (corregido /
  verificado correcto), Bloque C (verificados y declarados correctos, no tocar) y F-08 con
  la recomendación de `c-79-scoping-lectura-panel-academico`.
  - **F-01 / F-02** (denominadores del Dashboard y de la Cola) — **corregidos** (§4).
    Predicado compartido de "entra a la cola", tarjetas desde el catálogo de métricas,
    y test de coherencia cruzada que exige el mismo número en las tres pantallas.
  - **F-03** (filtro de archivadas) — **corregido** (§5). Pasó a tri-estado
    `false | true | todas`; el checkbox manda `todas`, que es lo que dice.
  - **F-04** (políticas de intentos) — **corregido** (§6). `ULTIMO`/`PRIMERO` ordenan por
    `creada_en` con desempate por `session_id`, no por el proxy anterior.
  - **F-05 / F-06** (acciones y estados de filtro) — **corregidos** (§7).
  - **F-07** (etiquetas muertas) — **corregido** (§8). Se removió la clave `pendiente` y se
    barrieron los `*_META`; los docstrings de RBAC ya no nombran roles eliminados en c-76.
  - **F-08** (scoping de LECTURAS del panel académico) — se decidió no tocarlo en este
    change (D5) y quedó cubierto por c-79, ya archivado.
  - **Bloque C** — verificado correcto, no se tocó.

  ### Hallazgos NUEVOS, encontrados durante la implementación

  - **H-01 (CRÍTICO, corregido)** — el write-back de notas a Moodle estaba **roto en
    silencio**. `comision.docente_id` quedó *viva pero congelada*: la migración 0086 la
    backfilleó a `comision_tutor` y la dejó, pero ningún endpoint la escribe desde
    entonces (cero escrituras en todo `backend/app`, verificado con grep). Los dos
    lectores que decidían **con qué credencial se firma la nota** y **qué sesiones se
    marcan sin credencial** la seguían consultando, así que toda comisión creada o
    gestionada desde la UI actual devolvía `sin_docente` y la nota **nunca llegaba al
    campus**. Corregido migrando ambos lectores a `comision_tutor` (ver 14.3).
  - **H-02 (corregido)** — la rendición habría salido VACÍA en modo sorteo por intento:
    `obtener_para_rendir` filtraba por `seleccionada`, y en ese modo todo el pool tiene
    `seleccionada=False`. Se agregó el filtro por el set del intento.
  - **H-03 (corregido)** — el denominador de la nota habría sido el pool entero y no el
    set del alumno: 10 de 10 bien sobre un pool de 30 daba 3,33 en vez de 10.
  - **H-04 (corregido)** — deuda de tests de tareas ya marcadas `[x]`: 6 de frontend
    (archivado tri-estado, `mostrar_eventos_alumno` en el patch, panel de integridad,
    `statProps` multilínea, `eliminarMateria`/`eliminarComision` ya inexistentes, y el
    subtítulo con `docente`) y 2 módulos de backend (`test_c76_registro_sesiones`,
    `test_c76_tutor_comision`) rojos por el scoping de coordinador de c-79, un email
    hardcodeado duplicado y una tabla faltante en un fixture. Todos verdes ahora.
  - **H-05 (corregido)** — `openspec validate` no pasaba: 5 specs nuevas del propio
    change usaban formato de spec completa en vez de delta.
  - **H-06 (abierto, NO es del proyecto)** — `src/lib/useUiPrefs.test.ts` tiene 4 rojos:
    **jsdom 25 no expone `localStorage` bajo Node 26**. Verificado con un test mínimo;
    forzar `--environment jsdom` tampoco lo arregla. Se resuelve actualizando jsdom o
    bajando Node, y no toca nada de este change.

- [x] 17.3 🔶 **Checkpoint con el dueño**: repasar el registro de hallazgos y confirmar la decisión sobre F-08 (change propio) antes de archivar.
- [x] 17.4 Guardar en engram el registro de hallazgos y las decisiones de diseño.
- [x] 17.5 **Devolución de notas al campus REAL, verificada de punta a punta** (26/8/2026)
  - `alumno.prueba3` entró por el link del campus, confirmó su cuenta, completó el perfil, se
    matriculó con el código, rindió (10 preguntas sorteadas de 30), entregó, y su nota llegó a
    Moodle: **userid 969, nota 30, firmada por `profesor_prueba`**, el docente del curso.
  - **El `dml_write_exception` era TRANSITORIO**, no un problema permanente del campus: la
    misma nota pasó de 5 (puesta a mano) a 30 (por el sistema). Antes fallaba todo intento de
    actualizar. Refuerza que el reintento tenga que existir.
  - **H-13 (corregido)**: una respuesta cloze con el TEXTO de la opción en vez de su id
    devolvía **201** al guardar y explotaba al **ENTREGAR** — el alumno terminaba el examen y
    no podía entregarlo, con la sesión sin finalizar y sin nota. Ahora se valida al entrar.
  - Verificado además: el reintento vuelve a tomar las fallidas; el gate de riesgo retiene sin
    revisar, **libera si el coordinador aprueba** y retiene si anula; el tutor puede marcar la
    nota como cargada a mano; las escalas 100/60 y 10/6 dan el mismo veredicto; y la revisión
    del alumno ya no le muestra la fórmula.

  - Guardado en cuatro entradas: `e06-replicacion`, `e07-sorteo-por-intento`,
    `writeback-credencial-nm` y el resumen de sesión.
