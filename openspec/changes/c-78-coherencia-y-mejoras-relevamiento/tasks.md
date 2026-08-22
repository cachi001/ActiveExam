# Tasks — c-78-coherencia-y-mejoras-relevamiento

> Reglas duras del proyecto aplicables a TODA tarea de este change:
> tests contra base real o efímera (**nunca** mock de DB), `extra='forbid'` en todo
> schema Pydantic nuevo, `snake_case` en Python, `PascalCase` en componentes React,
> Conventional Commits **sin** `Co-Authored-By`, no buildear ni commitear sin pedido
> explícito. Gobierno **MEDIO**: implementar por bloques y frenar en los checkpoints
> marcados 🔶 para que el dueño confirme antes de seguir.

## 1. Baja lógica de exámenes — persistencia

- [ ] 1.1 Agregar `eliminado_en: Mapped[str | None]` (TIMESTAMPTZ nullable, comentario "NULL = activo, NOT NULL = baja lógica") a `ExamenContenidoModel` en `backend/app/infrastructure/persistence/models/exam_content.py`, copiando la forma del comentario de `UsuarioModel.eliminado_en`.
- [ ] 1.2 Crear la migración Alembic `0083_c78_examen_contenido_eliminado_en.py`: `ADD COLUMN` aditiva y nullable, sin backfill; `downgrade` que dropea solo la columna, con nota de que el rollback pierde la marca de baja (los exámenes reaparecen; no se pierde dato de dominio).
- [ ] 1.3 Test de migración contra base efímera: aplicar `upgrade`, verificar que los exámenes preexistentes quedan con `eliminado_en` NULL y siguen listándose; aplicar `downgrade` y verificar que no toca ninguna otra tabla.

## 2. Baja lógica de exámenes — API

- [ ] 2.1 Agregar `estado: str = "activo"` (`activo` | `inactivo` | `todos`) a `ExamenContenidoSqlRepository.listar_paginado` (`backend/app/infrastructure/persistence/repositories/exam_content.py`), resolviendo el filtro en SQL sobre `eliminado_en` y asegurando que el `total` corresponde al conjunto filtrado.
- [ ] 2.2 Exponer el parámetro `estado` en `listar_examenes_contenido` (`backend/app/presentation/api/v1/exam_content/taking_router.py` — recordar que el listado del catálogo vive ahí, no en `catalog_router.py`), con default `activo`. Restringir `estado != "activo"` a principals staff/docente, igual que ya se hace con `materia_id`/`comision_id`.
- [ ] 2.3 Implementar `DELETE /{examen_id}` en `catalog_router.py`: gate `gestionar_academico` + `_exigir_pertenencia`, `204`, setea `eliminado_en = now()`, `404` si no existe o ya está de baja. Modelar sobre `eliminar_usuario` en `users/router.py`.
- [ ] 2.4 Implementar `POST /{examen_id}/reactivar`: mismo gate, setea `eliminado_en = NULL`, `404` si ya está activo. Modelar sobre `reactivar_usuario`.
- [ ] 2.5 Agregar las acciones de auditoría `EXAMEN_BAJA` y `EXAMEN_REACTIVAR` a `backend/app/application/audit/acciones.py` (módulo `EXAMENES`) y registrarlas con `registrar_seguro` en ambos endpoints, siguiendo el patrón de `MATERIA_BAJA`.
- [ ] 2.6 Excluir los exámenes dados de baja de `_contar_catalogo` en `backend/app/application/stats/resumen_service.py` (solo el conteo de **inventario**; `_session_conditions` y la actividad NO se tocan — ver design D2).
- [ ] 2.7 Tests de API contra base efímera: baja → `204` y desaparece del listado por defecto; segunda baja → `404`; `estado=inactivo` lo devuelve; `estado=todos` devuelve ambos; reactivar → vuelve al listado; reactivar un activo → `404`; sin capacidad → rechazo.
- [ ] 2.8 Test de invariante de evidencia: dar de baja un examen con sesiones rendidas y verificar que las sesiones, sus eventos y su evidencia siguen existiendo y son consultables por id, y que `total_sesiones` de Estadísticas NO cambió mientras `total_examenes` bajó en uno.

## 3. Baja lógica de exámenes — pantalla de Exámenes

- [ ] 3.1 Agregar `estado` a `listarExamenesContenidoPaginadoFn` en `frontend/src/lib/examContentCatalog.ts` y propagarlo como query param.
- [ ] 3.2 Agregar el selector de estado (activo / dado de baja / todos) al `FiltrosPanel` de `frontend/src/screens/ExamList.tsx`, cableado a `query.filters`.
- [ ] 3.3 Agregar al `ActionMenu` de cada fila la acción "Dar de baja" (examen activo) o "Reactivar" (dado de baja), con diálogo de confirmación que explique que el examen se oculta del catálogo pero su evidencia se conserva. Recargar la lista tras la operación.
- [ ] 3.4 Marcar visualmente las filas dadas de baja cuando el filtro las incluye, para que no se confundan con exámenes vigentes.
- [ ] 3.5 Agregar la opción de filtro de auditoría "Baja/reactivación de examen" al catálogo curado de `frontend/src/screens/Auditoria.tsx` (módulo Exámenes), con el patrón `examen.baja,examen.reactivar`.
- [ ] 3.6 🔶 **Checkpoint con el dueño**: demostrar el ciclo completo baja → invisible en Exámenes / Dashboard / picker de Notas / conteo de Estadísticas → reactivación, y confirmar que la semántica de la baja es la esperada antes de seguir con el bloque de coherencia.

## 4. Coherencia de denominadores (F-01, F-02)

- [ ] 4.1 En `frontend/src/screens/AdminDashboard.tsx`, aplicar el filtro de examen vinculado antes de contar `flagged`, usando el mismo predicado que `enriquecerYFiltrar` (`colaAgregacion.ts`). Extraer ese predicado a una función pura compartida para que exista **un solo** lugar donde vive la definición (design D3).
- [ ] 4.2 Reemplazar la `StatCard` hardcodeada de cola del Dashboard por `statProps('enColaRevision', …)`, y hacer que la tarjeta de exámenes también salga del catálogo (agregando la métrica a `STAT_META` si no existe).
- [ ] 4.3 Declarar el alcance de cada tarjeta de sesiones en su `sub`: el Dashboard cuenta actividad de cualquier estado; Registro de sesiones cuenta solo finalizadas.
- [ ] 4.4 En `backend/app/presentation/api/v1/proctoring/sessions/router.py`, calcular `en_cola_revision` de `/sessions/registro` excluyendo las sesiones sin examen vinculado. **No** cambiar el listado: esa pantalla lista sesiones de diagnóstico a propósito (desde ahí se borran).
- [ ] 4.5 Tests unitarios del predicado compartido de "entra a la cola" (sesión con examen y score sobre el umbral, sesión de diagnóstico sobre el umbral, sesión con examen bajo el umbral) y test de API del agregado de `/sessions/registro` contra base efímera.
- [ ] 4.6 Test de coherencia cruzada contra base efímera: con un dataset fijo que incluya sesiones de diagnóstico sobre el umbral, verificar que el conteo del Dashboard, el de la Cola de revisión y el `sesiones_en_riesgo` de Estadísticas dan el **mismo** número.

## 5. Filtro de archivadas tri-estado (F-03)

- [ ] 5.1 Cambiar `archivado: bool = False` por un parámetro tri-estado (`false` | `true` | `todas`) en `resultados_examen` (`catalog_router.py`), con `422` identificable para valores fuera del conjunto — mismo patrón que la validación ya existente de `estado_entrega`.
- [ ] 5.2 Mapear el valor `todas` a `archivado=None` en la llamada a `listar_resultados_examen` (el servicio ya lo soporta: `if archivado is not None`).
- [ ] 5.3 En `frontend/src/screens/exam-detail/ResultadosExamenPanel.tsx`, hacer que el checkbox "Mostrar archivadas" mande `todas` (no `true`), conservando `false` como default.
- [ ] 5.4 Tests de API: `false` → solo no archivadas; `true` → solo archivadas; `todas` → ambas con `total` correcto; valor inválido → `422`.

## 6. Políticas de intentos por tiempo real (F-04)

- [ ] 6.1 Proyectar `creada_en` de la sesión en la fila que consume `_aplicar_politica` (`backend/app/application/moodle/resultados_query.py` y/o el `select` de `sincronizar-moodle`).
- [ ] 6.2 Reescribir `_aplicar_politica` en `catalog_router.py` para que `ULTIMO`/`PRIMERO` ordenen por `creada_en` con desempate determinístico por `session_id`. Reemplazar el comentario que justificaba el proxy por uno que explique el criterio real.
- [ ] 6.3 Tests contra base efímera con un alumno de dos intentos donde el `session_id` ordena al revés que el tiempo: `ULTIMO` elige el más reciente, `PRIMERO` el más antiguo, `MAS_ALTA` sigue eligiendo por nota y `MANUAL` sigue sin deduplicar.

## 7. Acciones y estados de filtro (F-05, F-06)

- [ ] 7.1 En `ExamList.tsx`, corregir la acción "Configurar / vincular" para que navegue al examen de la fila (`/admin/examenes/{id}`) en lugar de a la página genérica de importación; si no existe destino de configuración por examen, retirarla del menú de fila y dejar la importación como acción de pantalla. Documentar cuál de las dos se eligió y por qué.
- [ ] 7.2 En `ExamList.tsx`, incluir el filtro de comisión en `hayFiltrosActivos` y en la condición del mensaje de vacío.
- [ ] 7.3 En `ResultadosExamenPanel.tsx`, incluir todos los filtros de la pantalla (estado, estado de entrega, archivado, rango de fechas) en la condición del mensaje de vacío.
- [ ] 7.4 Alinear el `ActionMenu` de la vista compacta de `ExamList.tsx` con el de escritorio (hoy le falta "Alumnos que rindieron").
- [ ] 7.5 Tests de componente de los estados de filtro: aplicar solo comisión habilita limpiar; filtro sin resultados muestra "ningún registro coincide"; base vacía sin filtros muestra "todavía no hay datos".

## 8. Barrido de etiquetas y documentación (F-07)

- [ ] 8.1 Remover la clave muerta `pendiente` de `DECISION_META` en `frontend/src/screens/admin/EstadisticasBody.tsx`, verificando primero contra el backend que el único centinela emitido es `sin_revisar`. Conservar el fallback legible para valores desconocidos.
- [ ] 8.2 Barrer los `*_META` restantes del frontend de administración (`ACCION_META`, `ETIQUETA_EVENTO`, `MODULO_LABELS`) buscando claves que el backend no emita y valores emitidos sin etiqueta. Corregir solo lo que esté desalineado (design D8: no rebautizar etiquetas que hoy son correctas).
- [ ] 8.3 Actualizar los docstrings de RBAC que nombran roles eliminados en c-76: `backend/app/presentation/api/v1/stats/router.py` (cabecera: "docente, admin_examenes"), `taking_router.py` (`listar_examenes_contenido`: "admin/proctor/..."), `catalog_router.py` (comentario de `create_exam_content_router`: "hoy docente, admin_examenes...").
- [ ] 8.4 Corregir el docstring de `archivar_resultado` que afirma "mismo scoping por comisión que el resto del panel": es cierto para las escrituras, falso para las lecturas (F-08). Dejarlo describiendo el estado real y referenciando el hallazgo.

---

# Relevamiento del 22/8/2026 (bloques 10 a 16)

> Absorbido desde el backlog del relevamiento. El detalle de cada task —causa, archivos,
> criterio de terminada y las decisiones ya cerradas por el dueño— está en
> [`relevamiento-2026-08-22.md`](relevamiento-2026-08-22.md), que es la fuente de esta
> lista. Acá van solo los checkboxes para no duplicar la prosa.
>
> **Ya resuelto y no se repite acá**: T-18 (auditoría con `null` y hashes) se solapa con
> el bloque 8 de este mismo change; lo que c-79 ya arregló (entidad, actor real, link al
> detalle) está hecho, y lo que falta está cubierto por 8.1 y 8.2.

## 10. Bugs a la vista

- [ ] 10.1 **T-19** Completar el registro dinámico LTI: que registrar la herramienta desde Moodle cree la fila con `activo=false` y un admin la habilite. Hoy se carga a mano y se pierde al recrear la base
- [ ] 10.2 **T-19** Chequeo de salud que avise si la allowlist LTI quedó vacía, antes de que lo descubra un alumno
- [ ] 10.3 **T-19** Pantalla de administración del allowlist LTI (hoy solo existe la API)
- [ ] 10.4 **T-17** Separar "cargó y está vacío" de "no pudo cargar" en `MateriasComisiones.tsx`: hoy un 401 se muestra como "No hay materias registradas"
- [ ] 10.5 **T-16** `change-password` re-emite el access token cuando cambió el `username`, para que tras el alta LTI la app muestre el usuario elegido y no `lti:1:7`

## 11. Alcance por rol

- [ ] 11.1 **T-07** Crear el rol PROFESOR con sus capacidades. NO emite veredicto (eso queda en COORDINADOR); el COORDINADOR conserva exámenes, banco y estadísticas
- [ ] 11.2 **T-02** Sacarle al TUTOR el acceso a Estadísticas, Creación de exámenes y Banco de preguntas, en el menú **y** en cada endpoint
- [ ] 11.3 **T-08** Filtros de materia, comisión y examen en Supervisión en vivo para coordinador y profesor; el tutor ve solo las suyas
- [ ] 11.4 **T-09** Registro de sesiones acotado al tutor, filtrando en la query del backend y no en el frontend

## 12. Configuración por examen

- [ ] 12.1 **T-01** Agregar `nunca` a `mostrar_nota` y hacerlo el default de un examen nuevo
- [ ] 12.2 **T-01** Botón "Publicar notas ahora" en el detalle del examen, con registro en auditoría de quién publicó y cuándo
- [ ] 12.3 **T-01** Bloquear la transición hacia atrás: publicar es camino de ida
- [ ] 12.4 **T-13** Opción por examen para mostrar u ocultar los eventos de proctoring al alumno mientras rinde, con default en NO

## 13. Materias, comisiones y exports

- [ ] 13.1 **T-14** Colapsar y desplegar cada comisión, en vez de tener todo abierto
- [ ] 13.2 **T-14** Paginación del listado de inscriptos (con 40 alumnos hoy es ilegible)
- [ ] 13.3 **T-14** Decidir acordeón contra página propia por comisión; de eso depende dónde vive el export
- [ ] 13.4 **T-03** Export de alumnos inscriptos por comisión en PDF y Excel, para cruzar contra Moodle
- [ ] 13.5 **T-15** Export de notas del examen
- [ ] 13.6 **T-15** Marcar el estado de la nota a mano, distinguiéndolo del confirmado por sincronización, con registro de quién lo marcó

## 14. Exámenes

- [ ] 14.1 **T-05** Crear un examen para varias comisiones, replicado (N exámenes independientes), en una operación todo o nada
- [ ] 14.2 **T-06** Duplicar un examen, sin arrastrar intentos, resultados ni destino de Moodle
- [ ] 14.3 **T-04** Dropear `comision.docente_id` una vez confirmado que ningún lector la usa (deuda que dejó c-79)

## 15. Armado del examen como Moodle (va al final)

- [ ] 15.1 **T-10** Guardar la definición del sorteo en el examen (categoría, subcategorías sí/no, cantidad, etiqueta) en vez de su resultado
- [ ] 15.2 **T-10** Resolver el set de preguntas por intento, al arrancar cada alumno, y persistirlo en el intento
- [ ] 15.3 **T-10** Vista previa de la pregunta tal como la ve el alumno, desde el banco y desde el armado
- [ ] 15.4 **T-10** Desglose en el armado: cuántas hay disponibles por categoría y cuántas se sortean
- [ ] 15.5 **T-10** Permitir mezclar tramos fijos y aleatorios en un mismo examen
- [ ] 15.6 **T-12** Validar el tope de preguntas contra las realmente disponibles, en el backend

## 16. Capacidad y rendimiento

- [ ] 16.1 **T-22** Correr la medición de carga contra el sistema real y escribir los resultados (hardware, punto de quiebre, configuración)
- [ ] 16.2 **T-20** Dimensionar el arranque de producción con los cores del plan una vez que deje de ser free, recalculando el pool (`workers × 24` conexiones contra `max_connections`)
- [ ] 16.3 **T-21** Que algo scrapee y guarde `/metrics` en producción, con retención que cubra el examen. Proteger el endpoint antes de exponerlo
- [ ] 16.4 Sacar los screenshots de base64 en Postgres: hoy un examen de 100 alumnos escribe ~360 MB en la base, y el depósito WORM de c-77 es **adicional**, no reemplaza
- [ ] 16.5 Mandar la captura binaria en vez de base64, que ahorra un tercio del tráfico y el trabajo de decodificar
- [ ] 16.6 Reemplazar el polling de 4 a 6 s por SSE (change c-15b), que baja a cero el costo de los paneles inactivos

## 17. Cierre

- [ ] 17.1 Verificar que `openspec validate` pasa para el change y que cada requisito de las specs tiene al menos un test que lo ejercita.
- [ ] 17.2 Redactar el registro de hallazgos final: F-01…F-07 con su estado (corregido / verificado correcto), Bloque C (verificados y declarados correctos, no tocar) y F-08 con la recomendación de `c-79-scoping-lectura-panel-academico`.
- [ ] 17.3 🔶 **Checkpoint con el dueño**: repasar el registro de hallazgos y confirmar la decisión sobre F-08 (change propio) antes de archivar.
- [ ] 17.4 Guardar en engram el registro de hallazgos y las decisiones de diseño (`topic_key: opsx/c-78-coherencia-y-mejoras-relevamiento/apply`).
