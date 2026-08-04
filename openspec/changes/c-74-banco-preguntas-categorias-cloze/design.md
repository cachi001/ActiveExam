## Context

Investigación hecha el 2026-08-01 leyendo el código real (no supuestos). Fuente:
`backend/app/infrastructure/persistence/models/exam_content.py`,
`backend/app/application/exam_content/{moodle_parser,import_service}.py`,
`backend/app/domain/exam_content/entities.py`,
`backend/app/application/exam_content/grade_calculator.py`,
`backend/app/presentation/api/v1/exam_content/catalog_router.py`,
`frontend/src/screens/Examen.tsx` + `examen/ExamenPreguntaCard.tsx`,
migraciones `0026`–`0051`.

### Modelo de datos actual

- `materia` (id, codigo, nombre, activa) — sin jerarquía interna.
- `comision` (id, materia_id, codigo, nombre, periodo, anio,
  codigo_matriculacion, activa, docente_id).
- `examen_contenido` (id, titulo, comision_id nullable, destino Moodle
  por-examen, config de rendición: tiempo_limite_min, intentos_permitidos,
  apertura/cierre, nota_maxima/aprobacion, `mezclar_preguntas` SIEMPRE true
  desde 0046, `limite_preguntas` nullable, mostrar_nota, revision_habilitada,
  politica_intentos). Es **a la vez** "lo que se importó de un XML" y "lo que
  rinde una comisión" — no hay separación entre banco y examen instanciado.
- `pregunta_examen` (id, examen_id, enunciado, `tipo` String(20) libre —hoy
  solo `multichoice`/`truefalse`—, orden, `seleccionada` bool desde 0031).
- `opcion_respuesta` (id, pregunta_id, texto, es_correcta, orden). Relación
  PLANA: 1 pregunta → N opciones → exactamente 1 correcta. El grading
  (`grade_calculator.py`) resuelve un único `{pregunta_id, opcion_elegida_id}`
  contra `OpcionRespuestaModel.es_correcta`.
- **No existe** ninguna tabla/columna de categoría, unidad o tema en ningún
  lado del esquema.

### Import Moodle XML (`moodle_parser.py`)

- `_TIPOS_SOPORTADOS = frozenset({"multichoice", "truefalse"})` — todo lo
  demás (incluido `cloze`/`multianswer`, `essay`, `matching`, `shortanswer`,
  `numerical`) cae a `omitidas` con motivo "tipo no soportado".
- `<question type="category">` → `continue` **sin registrar nada**, ni
  siquiera en el reporte de omitidas. El XML SÍ trae la ruta jerárquica
  (`$course$/top/Unidad 1/Subtema` en `<category><text>`), Moodle la coloca
  posicionalmente (no anidada) — todas las preguntas que siguen en el archivo
  hasta el próximo nodo `category` pertenecen a esa categoría.
- `_strip_html` elimina TODOS los tags del enunciado — incompatible con
  preservar los placeholders `{1:MULTICHOICE:...}` de cloze embebidos en
  `questiontext`, y con conservar formato HTML si se quisiera.
- `import_service.py`: convierte a la entidad de dominio `Pregunta`, aplica
  tope `limite_preguntas` (máx `LIMITE_PREGUNTAS_SISTEMA = 500`, rechaza el
  import completo si se excede, no trunca), persiste con `comision_id=None`
  (se asocia después).

### Armado del examen hoy (100% manual, sin sorteo)

- `GET /{examen_id}/preguntas` → pool completo, sin opciones/es_correcta (D3).
- `PATCH /{examen_id}/preguntas-seleccion` → docente manda la lista completa
  de ids seleccionados a mano. Valida: mínimo 1, no exceder `limite_preguntas`,
  y **queda bloqueada (409) si ya hay algún intento finalizado** en ese examen
  (`_seleccion_bloqueada` — evita alterar notas ya calculadas). Este candado
  es exactamente el mecanismo que necesitamos reusar para "un solo sorteo,
  fijo para toda la comisión".
- El "shuffle" que existe hoy es solo de ORDEN (preguntas y opciones), con
  semilla determinística por alumno — nunca de QUÉ preguntas entran.

### Frontend de rendición

- `ExamenPreguntaCard.tsx` asume siempre opción múltiple: enunciado como
  `<h2>` de texto plano + `.map` de opciones como radios. No hay branching
  por `tipo` — el campo ya viaja en el DTO pero se ignora.
- Estado de respuestas: `Record<string, string>` (pregunta_id → opcion_id),
  un solo valor por pregunta. Cloze necesita algo jerárquico (pregunta_id →
  {blank_id → valor}).

## Goals / Non-Goals

**Goals:**
- Separar conceptualmente "banco de preguntas de la materia" (persistente,
  categorizado) de "examen instanciado para una comisión" (un armado
  concreto, fijo una vez que alguien rinde).
- Aprovechar la info de categoría que Moodle YA manda en el XML (hoy se
  descarta) en vez de inventar una taxonomía propia desde cero.
- Reusar el candado de congelamiento post-intento que ya existe — no
  reinventar la lógica de "esto ya no se puede volver a tocar".
- Soportar cloze con grading parcial por blank (no todo-o-nada por pregunta).

**Non-Goals (de este change):**
- Auto-registro de alumnos vía Moodle/LTI — change separado, dominio CRITICAL.
- Selección aleatoria *por alumno* (cada uno con su propio sorteo) — se
  decidió explícitamente que NO: un sorteo único por comisión, todos rinden
  lo mismo.
- Editar preguntas del banco desde la UI (más allá de categorizarlas) — el
  banco se puede poblar por import de XML **o por sync desde la API de Moodle**;
  la creación manual de preguntas una por una no es goal.

## Decisions

Resueltas con criterio de mínimo riesgo/blast-radius: capa nueva ADITIVA sobre
las tablas actuales, sin remodelar `examen_contenido`/`pregunta_examen` (evita
el escenario BREAKING de la sección Risks). Se puede iterar hacia la
separación completa banco/examen en un change futuro si hace falta.

1. **`examen_contenido` NO cambia de rol.** El banco de preguntas vive como
   metadata ADITIVA sobre `pregunta_examen`: columna nueva `categoria_id`
   (nullable, FK a `categoria_pregunta`). Nada se remodela ni se migra de
   forma destructiva — un examen ya importado sigue funcionando idéntico,
   simplemente sus preguntas quedan con `categoria_id = NULL` ("Sin
   clasificar") hasta que el import (o un admin) las categorice.
2. **Tabla de categorías: autoreferencial simple.** `categoria_pregunta` (id,
   materia_id FK, nombre, categoria_padre_id nullable self-FK). Sin `ruta`/
   `path` materializado — a la escala de una materia (decenas de categorías,
   no miles) un recorrido recursivo simple alcanza; agregar `path` sin un caso
   de uso concreto que lo necesite sería sobre-ingeniería. Responde la Open
   Question de profundidad: soporta anidamiento arbitrario por construcción
   (no hay límite de 2 niveles fijo).
3. **Cloze: tabla nueva `pregunta_cloze_blank`** (id, pregunta_id FK a
   `pregunta_examen`, orden, tipo [`multichoice`|`shortanswer`|`numerical`],
   texto_antes, texto_despues) + `opcion_cloze_blank` (id, blank_id FK, texto,
   es_correcta, peso). Separada de `opcion_respuesta` (que sigue siendo
   exclusiva del modelo plano 1 pregunta → N opciones) para no forzarla a
   cargar con sub-estructura que no le corresponde. `Pregunta.tipo="cloze"`
   no tiene filas en `opcion_respuesta`, tiene N filas en
   `pregunta_cloze_blank`.
4. **API del armado aleatorio: persiste inmediatamente.** `POST
   /{examen_id}/sortear-preguntas` recibe `{categoria_ids: [...],
   cantidad_por_categoria: N}`, sortea UNA vez server-side y marca
   `seleccionada=true` en esas filas de `pregunta_examen` — reusa el `409` de
   `_seleccion_bloqueada` que ya existe para la selección manual (mismo
   candado, no hay selección manual Y sorteo compitiendo). Consistente con que
   config/selección en este sistema siempre es estado persistente, nunca
   calculado on-the-fly (D12).
5. **Preguntas ya importadas sin categoría**: quedan con `categoria_id = NULL`
   indefinidamente — la UI del banco las agrupa bajo un bucket fijo "Sin
   clasificar" por materia. Sin migración de datos ni re-clasificación
   forzada (responde la Open Question correspondiente).
6. **El armado aleatorio permite mezclar categorías desde el arranque**: el
   payload ya es una lista (`categoria_ids`), no una sola — "5 de Unidad 1 + 5
   de Unidad 2" es el caso normal, no una extensión futura.
7. **Pantalla nueva, separada del flujo de examen** (confirmado explícitamente
   por el owner): el banco de preguntas por categoría tiene su propia página
   (`/admin/banco-preguntas`), independiente de la pantalla de creación/edición
   de examen. La pantalla de examen solo consume categorías (para el sorteo),
   no las administra.

8. **Sync de categorías y preguntas desde la API de Moodle (sin import de XML).**
   El docente puede sincronizar el banco de preguntas directamente desde un curso
   de campustest sin necesidad de exportar/importar un XML. Flujo:
   - `POST /exam-content/moodle/sync-banco/{materia_id}` — recibe el `courseid`
     de Moodle y llama `core_question_get_bank_categories` (disponible desde
     Moodle 4.3) para traer la jerarquía de categorías, luego
     `core_question_get_questions_by_courses` o equivalente para las preguntas
     de cada categoría.
   - Persiste en las mismas tablas (`categoria_pregunta`, `pregunta_examen`,
     `opcion_respuesta`) que el import XML — misma representación interna,
     origen distinto. El campo `moodle_question_id` (int nullable en
     `pregunta_examen`) evita duplicados en re-syncs sucesivas.
   - El sorteo aleatorio (D4/task 3) funciona igual sin importar el origen de
     las preguntas — toma de `categoria_pregunta`, agnóstico del origen.
   - La credencial usada es la del docente (`moodle_credencial_docente`, que ya
     existe de C-73) — el token intercambia por WS y llama con los permisos del
     docente sobre su propio curso.
   - WS function a verificar en implementación: `core_question_get_bank_categories`
     (Moodle 4.3+, disponible en campustest 4.5). Fallback si no está habilitada:
     parsear el export XML (ya implementado). La pantalla admin muestra ambas
     opciones.

## Risks / Trade-offs

- [Cambiar la forma de `examen_contenido`/`pregunta_examen` es potencialmente
  BREAKING para exámenes ya importados] → Migración de datos, no solo de
  schema: hay que decidir qué pasa con los ~exámenes ya cargados hoy sin
  categoría (quedan en una categoría "Sin clasificar" por materia, probable).
- [Cloze es sustancialmente más trabajo que categorías+sorteo — toca grading,
  parser, y frontend a la vez] → Se prioriza banco+categorías+sorteo primero
  (resuelve el problema principal descrito por el usuario), cloze como
  segunda etapa sobre esa base ya existente.
- [El import de Moodle real puede traer variantes de sintaxis cloze no
  triviales (anidamiento, pesos parciales `%50%`, feedback embebido)] →
  Validar contra un XML real de cloze exportado desde el campus antes de
  fijar el parser, no diseñar a ciegas contra la spec de Moodle solamente.

## Open Questions

- ¿Las categorías son solo de 2 niveles (materia → unidad) o hace falta
  soportar sub-unidades anidadas como Moodle permite?
- ¿Qué pasa con las preguntas ya importadas HOY sin categoría — se re-clasifican
  a mano, o quedan en un bucket "Sin categoría" indefinidamente?
- ¿El armado aleatorio permite mezclar varias unidades en un mismo examen
  (ej. "5 de Unidad 1 + 5 de Unidad 2") desde el arranque, o la primera
  versión es una sola unidad por examen?
