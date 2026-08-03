## 1. Modelo de datos — categorías del banco de preguntas

- [ ] 1.1 Migración Alembic (rama `slim`): tabla `categoria_pregunta` (id,
      materia_id FK → `materia.id` ON DELETE CASCADE, nombre, categoria_padre_id
      nullable self-FK → `categoria_pregunta.id` ON DELETE CASCADE, creada_en).
      Índice en `(materia_id, categoria_padre_id)`.
- [ ] 1.2 Migración: columna `categoria_id` nullable en `pregunta_examen`, FK
      a `categoria_pregunta.id` ON DELETE SET NULL (una categoría borrada no
      debe borrar preguntas — quedan "Sin clasificar"). Aditiva, no rompe
      exámenes existentes (default NULL).
- [ ] 1.3 Modelo SQLAlchemy `CategoriaPreguntaModel` en
      `backend/app/infrastructure/persistence/models/exam_content.py`, relación
      self-referencial (`categoria_padre` / `subcategorias`).
- [ ] 1.4 Entidad de dominio `CategoriaPregunta` en
      `backend/app/domain/exam_content/entities.py` (o archivo nuevo
      `categorias.py` si `entities.py` ya es grande) — pura, sin ORM.
- [ ] 1.5 Test (RED→GREEN): crear categoría con padre, listar árbol por
      materia, borrar categoría con preguntas asociadas → preguntas quedan con
      `categoria_id=NULL` (no se borran). Sin mocks de DB.

## 2. Import de Moodle XML — dejar de descartar categorías

- [ ] 2.1 Test (RED): reproducir el bug actual — un XML con
      `<question type="category"><category><text>$course$/top/Unidad 1</text>`
      seguido de preguntas normales, y confirmar que HOY esas preguntas
      terminan sin ninguna categoría asociada (comportamiento actual,
      documentado antes de cambiarlo).
- [ ] 2.2 `moodle_parser.py`: trackear el nodo `category` activo durante el
      recorrido (variable de estado, NO se resetea entre preguntas — Moodle
      posiciona la categoría antes de las preguntas que le pertenecen, no las
      anida). Parsear la ruta (`$course$/top/Unidad 1/Subtema` → segmentos
      `["Unidad 1", "Subtema"]`, descartando el prefijo `$course$/top`).
- [ ] 2.3 `import_service.py`: resolver-o-crear la jerarquía de
      `categoria_pregunta` por ruta (memoizar dentro del import: la misma ruta
      repetida en el XML no debe crear categorías duplicadas), asignar
      `categoria_id` resultante a cada `Pregunta` que siga en el archivo.
- [ ] 2.4 Test: import de un XML con 2 categorías anidadas + preguntas
      intercaladas → cada pregunta queda con la categoría correcta; una
      segunda import del MISMO XML no duplica las categorías (idempotente por
      ruta+materia).
- [ ] 2.5 Preguntas sin categoría precedente en el XML (antes del primer nodo
      `category`, si el XML no empieza con uno) → `categoria_id=NULL`, mismo
      bucket "Sin clasificar" que las preguntas legacy (D5 de design.md).

## 3. Armado aleatorio de examen por categoría

- [ ] 3.1 Endpoint `POST /exam-content/{examen_id}/sortear-preguntas`,
      body `{categoria_ids: list[str], cantidad_por_categoria: int}` (D4/D6
      de design.md — lista, no un solo id).
- [ ] 3.2 Servicio: valida que cada `categoria_id` pertenece a la materia del
      examen; si `cantidad_por_categoria` excede las preguntas disponibles en
      esa categoría, error claro (no trunca en silencio, mismo criterio que
      `LIMITE_PREGUNTAS_SISTEMA` en el import).
- [ ] 3.3 Reusa `_seleccion_bloqueada` (candado 409 post-intento finalizado,
      YA EXISTE en `catalog_router.py`/servicio de selección) — el sorteo no
      puede pisar un examen que ya rindió alguien. Mismo candado que la
      selección manual, no uno paralelo.
- [ ] 3.4 El sorteo persiste de inmediato: marca `seleccionada=true` en las
      filas elegidas de `pregunta_examen` (D4) — no hay estado "sorteo
      calculado pero no guardado".
- [ ] 3.5 Test: sortear 5 de categoría A + 5 de categoría B → exactamente 10
      preguntas `seleccionada=true`, repartidas 5/5; repetir el sorteo sobre
      el mismo examen ANTES de que rinda alguien → resultado NUEVO (no es
      idempotente, cada sorteo es un evento); repetir DESPUÉS de un intento
      finalizado → 409, igual que la selección manual.
- [ ] 3.6 Frontend: en la pantalla de examen (no en la nueva pantalla del
      banco — D7), agregar la opción "Armar por sorteo" junto a la selección
      manual existente, con selector de categoría(s) + cantidad por
      categoría. Deshabilitada/oculta si el examen ya tiene un intento
      finalizado (mismo gate visual que ya existe para la selección manual).

## 4. Pantalla nueva — administración del banco de preguntas

- [ ] 4.1 Ruta nueva `/admin/banco-preguntas` (D7: separada del flujo de
      examen). Selector de materia → árbol de categorías (expandible,
      anidamiento arbitrario) → lista de preguntas de cada categoría
      (enunciado + tipo, sin opciones/es_correcta expuestas, mismo criterio
      D3 que ya aplica en `/preguntas`).
- [ ] 4.2 Bucket fijo "Sin clasificar" por materia, siempre visible al final
      del árbol si tiene preguntas (D5) — no se puede eliminar ni renombrar,
      es la categoría implícita.
- [ ] 4.3 Acción "Mover pregunta a categoría" (drag o selector) — la única
      edición manual de categorización permitida (el banco se puebla por
      import, no por creación manual de preguntas — Non-Goal de design.md).
- [ ] 4.4 CRUD de categorías (crear/renombrar/borrar) con el aviso claro de
      qué pasa con las preguntas al borrar una categoría con hijos (4.2).
- [ ] 4.5 Entrada de navegación nueva en el menú admin (`nav.ts` o
      equivalente) apuntando a la pantalla.
- [ ] 4.6 Test frontend: árbol renderiza anidamiento de 3 niveles, mover
      pregunta actualiza el árbol sin recargar toda la pantalla.

## 5. Cloze — modelo de datos y parser (segunda etapa, sobre la base de 1-4)

> Validar ANTES de fijar el parser (Risk de design.md): conseguir un XML real
> de cloze exportado de campustest.frm.utn.edu.ar y confirmar qué variantes de
> sintaxis aparecen de verdad (pesos parciales `%50%`, feedback embebido)
> antes de escribir 5.2. No diseñar el parser solo contra la spec de Moodle.

- [ ] 5.1 Migración: tablas `pregunta_cloze_blank` (id, pregunta_id FK,
      orden, tipo, texto_antes, texto_despues) + `opcion_cloze_blank` (id,
      blank_id FK, texto, es_correcta, peso) (D3 de design.md).
- [ ] 5.2 Parser de sintaxis `{N:TIPO:...}` en `moodle_parser.py` — a partir
      del XML real conseguido (ver nota arriba). Cubrir como mínimo
      `MULTICHOICE` y `SHORTANSWER`; documentar explícitamente qué variantes
      NO se soportan en esta primera vuelta (no hace falta el 100% de la spec
      Moodle).
- [ ] 5.3 `_TIPOS_SOPORTADOS` en `moodle_parser.py` agrega `"cloze"` /
      `"multianswer"`.
- [ ] 5.4 `_strip_html` no debe destruir los placeholders `{N:TIPO:...}`
      embebidos en `questiontext` de una pregunta cloze — ajustar para
      preservarlos (hoy los elimina como si fueran markup).
- [ ] 5.5 `Pregunta.__post_init__` (dominio): validación específica para
      cloze — al menos 1 blank, cada blank con al menos 1 opción y exactamente
      1 marcada correcta (o más de una si el tipo del blank lo permite).
- [ ] 5.6 Test: importar un XML real con preguntas cloze → se persisten con
      sus blanks y opciones, ninguna cae a "tipo no soportado".

## 6. Cloze — grading parcial por blank

- [ ] 6.1 `grade_calculator.py`: hoy resuelve un único
      `{pregunta_id, opcion_elegida_id}` contra `es_correcta` — agregar la
      rama cloze que recibe `{pregunta_id: {blank_id: opcion_elegida_id}}` y
      calcula nota = (blanks correctos / blanks totales) × peso de la
      pregunta (no todo-o-nada).
- [ ] 6.2 Test: pregunta cloze con 4 blanks, alumno responde 3 correctos y 1
      incorrecto → nota parcial 75% del peso de esa pregunta, no 0.
- [ ] 6.3 Test: blank sin respuesta (alumno lo dejó vacío) cuenta como
      incorrecto, no rompe el cálculo.

## 7. Cloze — frontend de rendición

- [ ] 7.1 Estructura de respuesta guardada pasa de `Record<pregunta_id,
      opcion_id>` a algo jerárquico que soporte cloze:
      `Record<pregunta_id, string | Record<blank_id, string>>` (unión, no se
      rompe el camino no-cloze existente).
- [ ] 7.2 Componente nuevo `PreguntaCloze.tsx`: renderiza el enunciado
      (`questiontext` ya parseado con los placeholders reemplazados por
      controles embebidos — selects/inputs inline, NO una lista de radios
      debajo del texto).
- [ ] 7.3 `ExamenPreguntaCard.tsx`: branching por `tipo` (hoy asume siempre
      opción múltiple) — cloze delega a `PreguntaCloze.tsx`, el resto sigue
      igual.
- [ ] 7.4 Test frontend: responder una pregunta cloze de 3 blanks, guardar,
      recargar la página → las 3 respuestas persisten (mismo contrato que hoy
      tiene el autoguardado de preguntas normales).

## 8. Cierre

- [ ] 8.1 Correr la suite completa (backend + frontend) — sin regresiones en
      exámenes multichoice/truefalse existentes (el modelo viejo no cambia de
      forma, solo se le agrega `categoria_id` nullable).
- [ ] 8.2 Probar en vivo contra un XML real de campustest con categorías +
      cloze mezclados con multichoice/truefalse.
- [ ] 8.3 Actualizar `knowledge-base/06_funcionalidades.md` si corresponde
      (nueva funcionalidad de armado por sorteo + banco categorizado).
