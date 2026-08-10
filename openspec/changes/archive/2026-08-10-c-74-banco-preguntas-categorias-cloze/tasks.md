## 1. Modelo de datos — categorías del banco de preguntas

- [x] 1.1 Migración Alembic (rama `slim`): tabla `categoria_pregunta` (id,
      materia_id FK → `materia.id` ON DELETE CASCADE, nombre, categoria_padre_id
      nullable self-FK → `categoria_pregunta.id` ON DELETE CASCADE, creada_en).
      Índice en `(materia_id, categoria_padre_id)`.
- [x] 1.2 Migración: columna `categoria_id` nullable en `pregunta_examen`, FK
      a `categoria_pregunta.id` ON DELETE SET NULL (una categoría borrada no
      debe borrar preguntas — quedan "Sin clasificar"). Aditiva, no rompe
      exámenes existentes (default NULL).
- [x] 1.3 Modelo SQLAlchemy `CategoriaPreguntaModel` en
      `backend/app/infrastructure/persistence/models/exam_content.py`, relación
      self-referencial (`categoria_padre` / `subcategorias`).
- [x] 1.4 Entidad de dominio `CategoriaPregunta` en
      `backend/app/domain/exam_content/entities.py` (o archivo nuevo
      `categorias.py` si `entities.py` ya es grande) — pura, sin ORM.
- [x] 1.5 Test (RED→GREEN): crear categoría con padre, listar árbol por
      materia, borrar categoría con preguntas asociadas → preguntas quedan con
      `categoria_id=NULL` (no se borran). Sin mocks de DB.

## 2. Import de Moodle XML — dejar de descartar categorías

- [x] 2.1 Test (RED): reproducir el bug actual — un XML con
      `<question type="category"><category><text>$course$/top/Unidad 1</text>`
      seguido de preguntas normales, y confirmar que HOY esas preguntas
      terminan sin ninguna categoría asociada (comportamiento actual,
      documentado antes de cambiarlo).
- [x] 2.2 `moodle_parser.py`: trackear el nodo `category` activo durante el
      recorrido (variable de estado, NO se resetea entre preguntas — Moodle
      posiciona la categoría antes de las preguntas que le pertenecen, no las
      anida). Parsear la ruta (`$course$/top/Unidad 1/Subtema` → segmentos
      `["Unidad 1", "Subtema"]`, descartando el prefijo `$course$/top`).
- [x] 2.3 `import_service.py`: resolver-o-crear la jerarquía de
      `categoria_pregunta` por ruta (memoizar dentro del import: la misma ruta
      repetida en el XML no debe crear categorías duplicadas), asignar
      `categoria_id` resultante a cada `Pregunta` que siga en el archivo.
- [x] 2.4 Test: import de un XML con 2 categorías anidadas + preguntas
      intercaladas → cada pregunta queda con la categoría correcta; una
      segunda import del MISMO XML no duplica las categorías (idempotente por
      ruta+materia).
- [x] 2.5 Preguntas sin categoría precedente en el XML (antes del primer nodo
      `category`, si el XML no empieza con uno) → `categoria_id=NULL`, mismo
      bucket "Sin clasificar" que las preguntas legacy (D5 de design.md).

## 3. Armado aleatorio de examen por categoría

- [x] 3.1 Endpoint `POST /exam-content/{examen_id}/sortear-preguntas`,
      body `{categoria_ids: list[str], cantidad_por_categoria: int}` (D4/D6
      de design.md — lista, no un solo id).
- [x] 3.2 Servicio: valida que cada `categoria_id` pertenece a la materia del
      examen; si `cantidad_por_categoria` excede las preguntas disponibles en
      esa categoría, error claro (no trunca en silencio, mismo criterio que
      `LIMITE_PREGUNTAS_SISTEMA` en el import).
- [x] 3.3 Reusa `_seleccion_bloqueada` (candado 409 post-intento finalizado,
      YA EXISTE en `catalog_router.py`/servicio de selección) — el sorteo no
      puede pisar un examen que ya rindió alguien. Mismo candado que la
      selección manual, no uno paralelo.
- [x] 3.4 El sorteo persiste de inmediato: marca `seleccionada=true` en las
      filas elegidas de `pregunta_examen` (D4) — no hay estado "sorteo
      calculado pero no guardado".
- [x] 3.5 Test: sortear 5 de categoría A + 5 de categoría B → exactamente 10
      preguntas `seleccionada=true`, repartidas 5/5; repetir el sorteo sobre
      el mismo examen ANTES de que rinda alguien → resultado NUEVO (no es
      idempotente, cada sorteo es un evento); repetir DESPUÉS de un intento
      finalizado → 409, igual que la selección manual.
- [x] 3.6 Frontend: en la pantalla de examen (no en la nueva pantalla del
      banco — D7), agregar la opción "Armar por sorteo" junto a la selección
      manual existente, con selector de categoría(s) + cantidad por
      categoría. Deshabilitada/oculta si el examen ya tiene un intento
      finalizado (mismo gate visual que ya existe para la selección manual).

## 4. Pantalla nueva — administración del banco de preguntas

- [x] 4.1 Ruta nueva `/admin/banco-preguntas` (D7: separada del flujo de
      examen). Selector de materia → árbol de categorías (expandible,
      anidamiento arbitrario) → lista de preguntas de cada categoría
      (enunciado + tipo, sin opciones/es_correcta expuestas, mismo criterio
      D3 que ya aplica en `/preguntas`).
- [x] 4.2 Bucket fijo "Sin clasificar" por materia, siempre visible al final
      del árbol si tiene preguntas (D5) — no se puede eliminar ni renombrar,
      es la categoría implícita.
- [x] 4.3 Acción "Mover pregunta a categoría" (drag o selector) — la única
      edición manual de categorización permitida (el banco se puebla por
      import, no por creación manual de preguntas — Non-Goal de design.md).
- [x] 4.4 CRUD de categorías (crear/renombrar/borrar) con el aviso claro de
      qué pasa con las preguntas al borrar una categoría con hijos (4.2).
- [x] 4.5 Entrada de navegación nueva en el menú admin (`nav.ts` o
      equivalente) apuntando a la pantalla.
- [x] 4.6 Test frontend: árbol renderiza anidamiento de 3 niveles, mover
      pregunta actualiza el árbol sin recargar toda la pantalla.

## 5. Cloze — modelo de datos y parser (segunda etapa, sobre la base de 1-4)

> Validar ANTES de fijar el parser (Risk de design.md): conseguir un XML real
> de cloze exportado de campustest.frm.utn.edu.ar y confirmar qué variantes de
> sintaxis aparecen de verdad (pesos parciales `%50%`, feedback embebido)
> antes de escribir 5.2. No diseñar el parser solo contra la spec de Moodle.

- [x] 5.1 Migración: tablas `pregunta_cloze_blank` (id, pregunta_id FK,
      orden, tipo, texto_antes, texto_despues) + `opcion_cloze_blank` (id,
      blank_id FK, texto, es_correcta, peso) (D3 de design.md).
- [x] 5.2 Parser de sintaxis `{N:TIPO:...}` en `moodle_parser.py` — a partir
      del XML real conseguido (ver nota arriba). Cubrir como mínimo
      `MULTICHOICE` y `SHORTANSWER`; documentar explícitamente qué variantes
      NO se soportan en esta primera vuelta (no hace falta el 100% de la spec
      Moodle).
- [x] 5.3 `_TIPOS_SOPORTADOS` en `moodle_parser.py` agrega `"cloze"` /
      `"multianswer"`.
- [x] 5.4 `_strip_html` no debe destruir los placeholders `{N:TIPO:...}`
      embebidos en `questiontext` de una pregunta cloze — ajustar para
      preservarlos (hoy los elimina como si fueran markup).
- [x] 5.5 `Pregunta.__post_init__` (dominio): validación específica para
      cloze — al menos 1 blank, cada blank con al menos 1 opción y exactamente
      1 marcada correcta (o más de una si el tipo del blank lo permite).
- [x] 5.6 Test: importar un XML real con preguntas cloze → se persisten con
      sus blanks y opciones, ninguna cae a "tipo no soportado".

## 6. Cloze — grading parcial por blank

- [x] 6.1 `grade_calculator.py`: hoy resuelve un único
      `{pregunta_id, opcion_elegida_id}` contra `es_correcta` — agregar la
      rama cloze que recibe `{pregunta_id: {blank_id: opcion_elegida_id}}` y
      calcula nota = (blanks correctos / blanks totales) × peso de la
      pregunta (no todo-o-nada).
- [x] 6.2 Test: pregunta cloze con 4 blanks, alumno responde 3 correctos y 1
      incorrecto → nota parcial 75% del peso de esa pregunta, no 0.
- [x] 6.3 Test: blank sin respuesta (alumno lo dejó vacío) cuenta como
      incorrecto, no rompe el cálculo.

## 7. Cloze — frontend de rendición

- [x] 7.1 Estructura de respuesta guardada pasa de `Record<pregunta_id,
      opcion_id>` a algo jerárquico que soporte cloze:
      `Record<pregunta_id, string | Record<blank_id, string>>` (unión, no se
      rompe el camino no-cloze existente).
- [x] 7.2 Componente nuevo `PreguntaCloze.tsx`: renderiza el enunciado
      (`questiontext` ya parseado con los placeholders reemplazados por
      controles embebidos — selects/inputs inline, NO una lista de radios
      debajo del texto).
- [x] 7.3 `ExamenPreguntaCard.tsx`: branching por `tipo` (hoy asume siempre
      opción múltiple) — cloze delega a `PreguntaCloze.tsx`, el resto sigue
      igual.
- [x] 7.4 Test frontend: responder una pregunta cloze de 3 blanks, guardar,
      recargar la página → las 3 respuestas persisten (mismo contrato que hoy
      tiene el autoguardado de preguntas normales).

## 9. Sync de banco de preguntas desde la API de Moodle (D8) — DESCARTADO

> Esta sección se marcó `[x]` en su momento pero implementaba una decisión
> (D8) que resultó técnicamente inviable: `core_question_get_bank_categories`
> y `core_question_get_questions_by_courses` NO EXISTEN en ningún branch del
> core de Moodle (verificado contra `moodle/moodle` main y MOODLE_405_STABLE).
> Se evaluaron y descartaron scraping HTTP del export y el workaround vía
> `mod_quiz` (ver D8 en design.md). El import de XML ya cubre el objetivo
> (preguntas + categorías juntas, estructurado, sin credenciales adicionales).
> Todo el código de esta sección fue **eliminado**:
> `moodle_sync_service.py`, endpoint `POST /exam-content/moodle/sync-banco`,
> schemas `SyncBancoRequest`/`SyncBancoResponse`, diálogo "Sincronizar desde
> campus" del frontend, y los tests que ejercitaban ese código
> (`test_c74_moodle_sync.py` completo, sección sync de
> `test_c74_propiedad_organizacion.py`).

- [x] 9.1 Migración: columna `moodle_question_id` (int nullable) en
      `pregunta_examen` — se mantiene, la usa el import de XML para
      idempotencia (no es exclusiva del sync descartado).
- [x] 9.2 Verificado en campustest y contra el código fuente de Moodle: no
      hay WS de banco de preguntas disponible en ninguna versión.
- [x] ~~9.3 `moodle_sync_service.py`~~ — eliminado, no aplica (decisión tomada, no pendiente).
- [x] ~~9.4 Endpoint `POST /exam-content/moodle/sync-banco`~~ — eliminado, no aplica.
- [x] ~~9.5 Test de sync idempotente~~ — eliminado, no aplica.
- [x] ~~9.6 Botón "Sincronizar desde campus" en frontend~~ — eliminado, no aplica.

## 8. Cierre

- [x] 8.1 Correr la suite completa (backend + frontend) — sin regresiones en
      exámenes multichoice/truefalse existentes (el modelo viejo no cambia de
      forma, solo se le agrega `categoria_id` nullable).
- [x] 8.2 Probar en vivo contra un XML real de campustest con categorías +
      cloze mezclados con multichoice/truefalse.
- [x] 8.3 Actualizar `knowledge-base/06_funcionalidades.md` si corresponde
      (nueva funcionalidad de armado por sorteo + banco categorizado).

## 10. Fixes E2E post-implementación (verificación en vivo contra campustest)

Encontrados y arreglados durante la verificación en vivo del examen cloze
completo (E2E: importar → rendir → revisar → sincronizar), ninguno tenía
cobertura de test previa.

- [x] 10.1 `_strip_html` (moodle_parser.py) pegaba palabras al borrar tags de
      bloque sin salto literal en el XML fuente (bug real reportado en vivo) —
      3 bugs encadenados: glue de palabras, entidades HTML sin decodificar
      (`&lt;`), `&nbsp;` sin colapsar como línea en blanco. Tests:
      `test_c74_strip_html_boundaries.py` (12 casos).
- [x] 10.2 Estilo de código en cloze/multichoice no distinguía consigna de
      código dado — se agregaron marcadores `CODE_MARCA_INICIO/FIN` (preservan
      los `<code>` reales del XML) + fondo propio en la caja de enunciado,
      replicando el resaltado de Moodle. `renderTextoConCodigo.tsx` nuevo.
- [x] 10.3 Tamaño y peso de fuente inconsistentes entre multichoice/truefalse
      (20px `title-lg`) y cloze (15px `body-md`) — unificados a `body-md` +
      `font-semibold` en ambos.
- [x] 10.4 Token de color `warning` (`tailwind.config.js`) apuntaba a `700`
      (`#b45309`, oscuro) en vez de `500` (`#f59e0b`, el ámbar de referencia
      usado en la verificación biométrica) — corregido en el token único,
      propaga a toda la app.
- [x] 10.5 `obtener_revision()` (revision_query.py) leía respuestas cloze
      intentando `json.loads()` un blob en `respuesta_alumno.opcion_elegida_id`
      — las respuestas cloze viven en `respuesta_alumno_cloze` (tabla propia,
      una fila por blank) desde que se separó de `respuesta_alumno`. Resultado
      visible: la nota aparecía bien pero el detalle marcaba todo "sin
      responder"/0 correctas. Tests: `test_c74_revision_cloze.py` (2 casos).
- [x] 10.6 Revisión de respuestas (`ExamenRevision.tsx`) para cloze mostraba el
      enunciado crudo sin parsear (placeholders `{N:TIPO:...}` literales) Y
      duplicaba el texto de transición entre huecos (`texto_despues` se
      renderizaba en cada blank en vez de solo en el último). Reescrito como
      párrafo continuo, igual que `PreguntaCloze.tsx` en la rendición.
- [x] 10.7 Aislamiento por comisión entre docentes de una misma materia — tres
      bugs de autorización, cero cobertura previa: (a) `_exigir_pertenencia_materia`
      comparaba contra un docente ARBITRARIO de la materia (`.limit(1)`), no
      contra membresía real → falso negativo a un docente real; (b)
      `crear-desde-banco` no validaba que `comision_id` fuera una comisión del
      docente (solo materia) → podía crear examen para la comisión de OTRO
      docente; (c) `POST /{examen_id}/comision` no tenía NINGÚN chequeo de
      pertenencia. Arreglado con `autorizar_docente_sobre_materia` (booleano de
      membresía) + `autorizar_docente_sobre_comision` (nuevo) +
      `es_docente_de_materia()` (reemplaza `docente_de_materia()`). Tests:
      `test_c74_autorizacion_materia_comision.py` (8 casos puros) +
      `test_c74_pertenencia_comision_banco.py` (5 casos de integración).
- [x] 10.8 Sincronización con Moodle verificada end-to-end contra el curso real
      ZZ-TEST-ActiveExam (courseid=7, cmid=537, `mod_assign`): nota 100/100
      escrita y confirmada en la interfaz de calificación de Moodle.
