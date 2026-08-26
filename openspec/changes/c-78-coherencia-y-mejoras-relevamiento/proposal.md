## Why

La superficie de administración ya está construida (C-20, C-69…C-77), pero **nunca se auditó de punta a punta si lo que muestra es lo que hay en la base**. Un número que no responde al filtro que la persona acaba de aplicar, o dos pantallas que dicen "Sesiones" sobre denominadores distintos, no son un detalle estético: son una pérdida de confianza en el tablero completo, y en un sistema L2.5 —donde el número solo PRIORIZA revisión humana— un número en el que no se puede confiar rompe el único mecanismo que el producto ofrece.

El disparador concreto: **el catálogo de exámenes (`examen_contenido`) no tiene ninguna forma de dar de baja un examen**. No hay DELETE en `catalog_router.py`, no hay `eliminado_en`, no hay flag `activo`. La última sesión terminó con un examen borrado **a mano por SQL directo contra el Postgres de producción**, porque no existía otro camino. Eso es un agujero operativo confirmado, no una hipótesis.

Además, el fix de etiquetas ya mergeado en `main` (`930e1a1 fix: normaliza etiquetas de eventos/acciones en Auditoria y Estadisticas`) resolvió UN caso de una clase de bug —valor interno filtrándose a la UI, o etiqueta que no describe la semántica real— que nunca se barrió sistemáticamente. Esta auditoría barre la clase entera.

Este change NO agrega features de producto. Es **auditoría + corrección de coherencia** sobre lo ya construido.

## What Changes

### Bloque A — Baja lógica de exámenes (gap confirmado, gobierno MEDIO)

- **Se agrega `eliminado_en` a `examen_contenido`**, siguiendo *exactamente* la convención que ya existe en el proyecto (`usuario`, `sesion`, `embedding_referencia`, `foto_referencia`): `NULL` = activo, `NOT NULL` = baja lógica. **No se inventa una convención nueva** ni se usa el booleano `activa` de `materia`/`comision` (ver design D1).
- `DELETE /api/v1/exam-content/{examen_id}` → baja lógica (204). `POST /api/v1/exam-content/{examen_id}/reactivar` → reactivación. Modelados sobre `DELETE /users/{id}` + `POST /users/{id}/reactivar`, que ya implementan este patrón completo.
- El listado del catálogo gana un filtro `estado` (`activo` default | `inactivo` | `todos`), idéntico al de `GET /users`. La pantalla **Exámenes** gana el selector de estado y la acción de baja/reactivación en su `ActionMenu`.
- **Todo consumidor del catálogo excluye los dados de baja por defecto**: listado paginado, conteo `total_examenes` de Estadísticas, picker en cascada de Notas, catálogo del alumno. La evidencia y las sesiones históricas del examen dado de baja **quedan intactas** (regla dura #6/#7: la baja es administrativa, nunca destruye cadena de custodia).

### Bloque B — Coherencia de números entre pantallas (hallazgos confirmados de la auditoría)

Los detalles y la traza de cada hallazgo están en `design.md` §Hallazgos. Resumen de lo que se corrige:

- **F-01 — "Cola de revisión" cuenta cosas distintas en tres pantallas.** El Dashboard cuenta *todas* las sesiones con `score >= umbral`, **incluidas las de diagnóstico** (`modo='test'`, sin examen); la Cola de revisión real las **excluye** (`enriquecerYFiltrar`); Registro de sesiones cuenta solo **finalizadas**. Tres denominadores, un solo nombre. Se unifica el criterio: "entra a la Cola de revisión" = lo que la Cola de revisión efectivamente lista.
- **F-02 — El Dashboard esquiva `statCatalog`.** `statCatalog.ts` existe justamente como fuente única de label/ícono/tono por métrica, y el Dashboard hardcodea la tarjeta de cola (`flag` / "Cola de revisión" / `warning`) mientras Registro de sesiones usa la canónica (`gavel` / "Sobre el umbral de riesgo" / `error`). Misma métrica, dos vocabularios.
- **F-03 — El filtro "Mostrar archivadas" muestra SOLO las archivadas.** El checkbox manda `archivado=true` y el backend hace `WHERE archivado IS true`, ocultando las no archivadas. La etiqueta promete *incluir*; el comportamiento es *reemplazar*. El backend ya soporta `archivado=None` = todas, pero el router lo tipa `bool = False` y ese valor es inalcanzable por HTTP. **BREAKING (contrato de query param)**: `archivado` pasa a tri-estado.
- **F-04 — "Último intento" / "Primer intento" no ordenan por tiempo.** `_aplicar_politica` desempata por `session_id` (UUID v4, aleatorio) usándolo como proxy de orden temporal — el propio comentario del código lo admite. Con múltiples intentos, la política de write-back a Moodle elige una fila **al azar**. `creada_en` existe y ya se usa en Estadísticas. Es un bug de datos que llega hasta la nota del alumno en Moodle.
- **F-05 — "Configurar / vincular" ignora el examen de la fila.** En **Exámenes**, esa acción del `ActionMenu` navega a `/admin/examenes/importar` (la página genérica de importación), descartando `e.id`. La acción no hace lo que su etiqueta dice sobre la fila en la que se abrió.
- **F-06 — Detección de "hay filtros activos" incompleta.** En **Exámenes**, `hayFiltrosActivos` ignora el filtro de comisión; en el panel de resultados, el mensaje de vacío solo mira `q` y `estado`. Filtrar por comisión (o por fecha/archivado) y ver "Todavía no hay exámenes cargados" es indistinguible de una base vacía.
- **F-07 — Etiquetas muertas y docstrings que nombran roles eliminados.** `DECISION_META.pendiente` en Estadísticas mapea un valor que el backend nunca emite (usa el centinela `sin_revisar`); los docstrings de `stats/router.py` y del listado del catálogo siguen nombrando `docente`, `admin_examenes` y `proctor`, roles **eliminados del dominio en c-76**. Es exactamente la clase de deriva que arrancó `930e1a1`.

### Bloque C — Verificados y declarados CORRECTOS (no se tocan)

La auditoría también sirve para dejar por escrito qué **no** es un bug, para que nadie lo "arregle" después:

- **Archivar/desarchivar resultados** (`archivarResultadoFn`, `ProctoringSessionModel.archivado`) es intencional y razonable: soft-hide administrativo de intentos duplicados o de prueba, sin borrar nada, auditado (`sesion.resultado.archivar`). **No confundir con la baja lógica de exámenes del Bloque A** — son cosas distintas a niveles distintos. Solo se corrige la semántica de su filtro (F-03).
- **`_contar_catalogo` acotado por filtro** en Estadísticas es correcto y deliberado: las tarjetas de inventario responden al recorte de materia/comisión/examen, pero **no** al de fechas (un examen existe se haya rendido o no en ese rango).
- **El filtro `accion` de Auditoría acepta listas separadas por coma** y las combina con `OR` — la agrupación de la UI ("Cambio de estado" = `user.delete,user.reactivate`) está correctamente soportada server-side.
- **Las bandas de score de Estadísticas se derivan del umbral vivo** (`bandas_de_score`), así que "última banda" y "en riesgo" no pueden desalinearse por construcción.

### Bloque D — Hallado pero FUERA DE ALCANCE (se recomienda change propio)

- **F-08 — Los endpoints de LECTURA del panel académico no están acotados por comisión.** `GET /{examen_id}/resultados`, `GET /{examen_id}/config`, `GET /{examen_id}/preguntas` y `GET /comisiones/{id}/alumnos` **no** llaman a `_exigir_pertenencia`, mientras que *todas* las escrituras equivalentes sí. Un tutor puede **leer** los resultados y la configuración de exámenes de comisiones que no dicta; solo no puede escribirlos. El docstring de `archivar_resultado` incluso afirma "mismo scoping por comisión que el resto del panel", lo cual hoy no es cierto para las lecturas. Esto es **RBAC/acceso a datos de alumnos → gobierno CRÍTICO**, y decidir si es un bug o el diseño querido (¿el tutor debe ver el rendimiento de toda la materia?) es una **decisión del dueño**, no de una auditoría de coherencia. Se documenta y se recomienda `c-79-scoping-lectura-panel-academico`.

### Bloque E — Relevamiento del 22/8/2026 (absorbido)

El dueño recorrió el sistema y salieron 22 hallazgos. Se absorben acá porque comparten
naturaleza con los bloques A a D: son incoherencias y huecos sobre lo ya construido, no
producto nuevo. Los que sí son producto nuevo (rol PROFESOR, sorteo aleatorio) se
declaran como capacidades nuevas más abajo.

- **E-01 — La nota se muestra sola al terminar.** El flujo real del docente es revisar y
  después publicar. Hoy no existe la acción de publicar: solo un enum que nadie sabe
  cuándo tocar.
- **E-02 — El alumno ve todos los eventos de proctoring mientras rinde.** Sin forma de
  desactivarlo.
- **E-03 — El TUTOR ve Estadísticas, Creación de exámenes y Banco de preguntas.** No le
  corresponden.
- **E-04 — Falta el rol PROFESOR.** Hoy hay que elegir entre tutor (muy poco) y
  coordinador (demasiado, incluye el veredicto).
- **E-05 — Supervisión en vivo y Registro de sesiones no filtran por materia/comisión.**
- **E-06 — Un examen sirve a una sola comisión** y no se puede duplicar.
- **E-07 — El sorteo de preguntas es de armado, no de rendición.** Todos los alumnos
  reciben exactamente las mismas preguntas; Moodle sortea por intento.
- **E-08 — No hay vista previa de la pregunta** ni desglose de lo que se está eligiendo.
- **E-09 — El tope de preguntas no se valida** contra las realmente disponibles.
- **E-10 — No se pueden exportar** los inscriptos por comisión ni las notas, y sin API de
  Moodle la nota queda "pendiente" para siempre aunque se haya cargado a mano.
- **E-11 — Materias y comisiones es ilegible** con 40 inscriptos: sin colapsar, sin paginar.
- **E-12 — El registro LTI es manual** y se pierde al recrear la base, dejando el ingreso
  desde el campus caído para todos, sin aviso.
- **E-13 — Tres bugs a la vista**: la pantalla de materias muestra "no hay nada" cuando en
  realidad falló la carga; tras el alta LTI la sesión muestra `lti:1:7` en vez del usuario
  elegido; Auditoría sigue mostrando campos crudos.
- **E-14 — Capacidad sin medir.** El backend corre un proceso en 0,1 de CPU, nadie scrapea
  `/metrics`, y los screenshots se guardan como base64 cifrado en Postgres: un examen de
  100 alumnos escribe unos 360 MB en la base.

## Capabilities

### New Capabilities
- `visibilidad-resultados-alumno`: la nota y los eventos de proctoring son invisibles para el alumno por defecto; la nota se publica por una acción humana explícita y auditada.
- `rol-profesor-y-alcance`: rol PROFESOR con gestión académica y supervisión, SIN veredicto de integridad; y alcance por pertenencia en supervisión en vivo y registro de sesiones.
- `armado-examen-aleatorio`: el examen guarda la DEFINICIÓN del sorteo, no su resultado, y cada alumno recibe su propio set al iniciar el intento.
- `exportables-academicos`: exportar inscriptos por comisión y notas del examen, y marcar el estado de la nota a mano cuando no hay API del campus.
- `lti-registro-dinamico`: registrar la herramienta desde Moodle crea la fila de confianza en estado inactivo; un admin la habilita.
- `exam-catalog-soft-delete`: Baja lógica y reactivación de `examen_contenido` con `eliminado_en`, filtro de estado en el catálogo y exclusión por defecto en todos sus consumidores, sin tocar la evidencia ni las sesiones históricas.
- `stat-denominator-coherence`: Una métrica con el mismo nombre SHALL contar lo mismo en toda la superficie de administración; el vocabulario (label/ícono/tono) sale siempre de la fuente única `statCatalog`.
- `filtro-etiqueta-fiel`: Un control de filtro SHALL hacer lo que su etiqueta dice — "mostrar X" incluye X además de lo ya visible, y el estado "hay filtros aplicados" SHALL considerar todos los filtros que la pantalla ofrece.

### Modified Capabilities
- `exam-content-model`: `examen_contenido` gana la columna `eliminado_en` (nullable, `NULL` = activo) como estado de baja lógica del catálogo.
- `statistical-distribution-analytics`: los conteos de catálogo excluyen los exámenes dados de baja; los denominadores de sesiones se declaran explícitamente (diagnóstico excluido) y se alinean con los del resto de las pantallas.
- `subida-nota-individual-lote`: las políticas de intentos `ULTIMO` y `PRIMERO` ordenan por `creada_en` (tiempo real), no por `session_id`; y el estado de la nota admite marcado manual, distinguible del confirmado por sincronización.
- `permisos-nm-pertenencia` (de c-79): se le suma el rol PROFESOR y se le saca al TUTOR la gestión de exámenes y banco.
- `exam-content-model`: un examen se puede crear replicado para varias comisiones y se puede duplicar.

## Impact

- **Migración Alembic (`0083`)**: `ALTER TABLE examen_contenido ADD COLUMN eliminado_en TIMESTAMPTZ NULL`. **Aditiva, no destructiva** — no requiere el procedimiento de dos pasos (regla de migraciones destructivas del proyecto).
- **Backend — catálogo**: `app/presentation/api/v1/exam_content/catalog_router.py` (nuevo DELETE + reactivar), `taking_router.py` (`listar_examenes_contenido` + filtro `estado`), `app/infrastructure/persistence/repositories/exam_content.py` (`listar_paginado`), `app/infrastructure/persistence/models/exam_content.py` (`ExamenContenidoModel`).
- **Backend — stats**: `app/application/stats/resumen_service.py` (`_contar_catalogo` excluye dados de baja), `app/presentation/api/v1/stats/router.py` (docstring de roles).
- **Backend — resultados**: `app/presentation/api/v1/exam_content/catalog_router.py` (`resultados_examen`: `archivado` tri-estado; `_aplicar_politica`: orden por `creada_en`), `app/application/moodle/resultados_query.py` (query de resultados; la fila ya expone `creada_en` de la sesión o se agrega al proyectado).
- **Frontend**: `screens/AdminDashboard.tsx` (denominador + `statCatalog`), `screens/ExamList.tsx` (estado, baja/reactivación, acción "Configurar / vincular", `hayFiltrosActivos`), `screens/exam-detail/ResultadosExamenPanel.tsx` (checkbox tri-estado, mensaje de vacío), `screens/admin/EstadisticasBody.tsx` (etiqueta muerta), `lib/examContentCatalog.ts` (param `estado`), `screens/proctoring/statCatalog.ts` (métrica de cola).
- **Auditoría**: la baja y la reactivación de examen registran entradas nuevas (`examen.baja` / `examen.reactivar`, módulo `EXAMENES`), siguiendo el patrón de `MATERIA_BAJA`. Sumar la opción al filtro curado de `Auditoria.tsx`.
- **NO impacta**: la cadena de custodia, el motor de scoring, la decisión humana de revisión, ni el contrato de rendición del alumno. Ningún dato se borra físicamente.
- **NO impacta**: C-03 (sin dependencia de la arquitectura de mensajería).
