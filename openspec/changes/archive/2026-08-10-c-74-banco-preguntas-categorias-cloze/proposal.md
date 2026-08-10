## Why

Hoy el import de un banco de preguntas Moodle XML trae **todas** las preguntas
mezcladas en un solo `examen_contenido`, sin ninguna noción de categoría/unidad
— aunque el XML de Moodle sí trae esa información (`<question type="category">`
con la ruta `$course$/Unidad 1/Subtema`) y hoy se descarta en silencio. Armar un
examen es 100% manual: el docente tilda preguntas una por una. No hay forma de
decir "armame un examen con 10 preguntas al azar de la Unidad 3" — que es
exactamente cómo se arma un examen en Moodle usando su banco de preguntas por
categorías + la pregunta "aleatoria" (`random`).

Además, el sistema hoy solo soporta preguntas `multichoice`/`truefalse`. La
mayoría de los cuestionarios reales que se van a importar desde Moodle son
formato **cloze** (completar el texto con opciones embebidas,
`{1:MULTICHOICE:...}`) — hoy esas preguntas se descartan como "tipo no
soportado" en el import.

## What Changes

- Nueva jerarquía de **categorías del banco de preguntas** (materia → categoría
  → subcategoría, tipo Moodle), persistente y reutilizable entre imports —
  separada del concepto de "examen que rinde una comisión".
- El import de Moodle XML deja de descartar los nodos `category`: los usa para
  clasificar cada pregunta importada en su categoría/unidad correspondiente
  (resolviendo/creando la jerarquía por ruta).
- Pantalla de administración del banco de preguntas por materia → categoría →
  unidad (fuera del flujo de "crear examen").
- **Armado aleatorio de examen por comisión**: el docente elige materia +
  comisión + unidad(es) + cantidad de preguntas por unidad, el sistema sortea
  UNA vez y ese conjunto queda fijo para toda la comisión (mismo mecanismo de
  congelamiento que ya existe hoy tras el primer intento finalizado — no hace
  falta reinventarlo, se reusa).
- **BREAKING (modelo de datos)**: separar "banco de preguntas importado" de
  "examen instanciado para una comisión" — hoy son la misma entidad
  (`examen_contenido` + `pregunta_examen.seleccionada`). Necesita decisión de
  diseño explícita antes de tocar código (ver `design.md`).
- Soporte de preguntas **cloze** (Moodle `type="cloze"`/`multianswer`): nuevo
  sub-modelo de "blanks" por pregunta, parser de la sintaxis `{N:TIPO:...}` de
  Moodle, grading por blank (no por pregunta completa), y un componente de
  frontend nuevo para renderizar el enunciado con controles embebidos.

## Capabilities

### New Capabilities
- `question-bank-categories`: jerarquía de categorías/unidades del banco de
  preguntas por materia, poblada desde el import de Moodle XML y editable a
  mano. Incluye la pantalla de administración del banco.
- `random-exam-assembly`: armado de un examen por sorteo (materia + comisión +
  unidad(es) + cantidad), sorteo único por comisión, con el mismo candado de
  congelamiento post-intento que ya existe para la selección manual.
- `cloze-question-type`: preguntas con blanks embebidos en el texto — modelo
  de datos, parser de import, grading parcial por blank, render de frontend.

### Modified Capabilities
- `moodle-xml-import`: deja de descartar `<question type="category">`; agrega
  soporte de `type="cloze"`/`multianswer` (hoy explícitamente fuera de
  `_TIPOS_SOPORTADOS` en `moodle_parser.py`).
- `exam-content-model`: separación banco-de-preguntas vs. examen-instanciado
  (hoy `examen_contenido`/`pregunta_examen` cumplen ambos roles a la vez).

## Impact

**Backend:**
- `backend/app/infrastructure/persistence/models/exam_content.py` — nueva(s)
  tabla(s) de categoría y de blanks de cloze; posible remodelado de
  `examen_contenido`/`pregunta_examen` (ver design.md).
- `backend/app/application/exam_content/moodle_parser.py` — trackear el nodo
  `category` activo durante el recorrido del XML; parser de sintaxis cloze.
- `backend/app/application/exam_content/import_service.py` — resolver/crear
  categorías, pasar blanks de cloze a la entidad de dominio.
- `backend/app/domain/exam_content/entities.py` — validación de dominio nueva
  para cloze (hoy `Pregunta.__post_init__` no distingue cloze de "tipo
  desconocido genérico").
- `backend/app/application/exam_content/grade_calculator.py` — grading por
  blank para cloze (hoy resuelve un único `{pregunta_id, opcion_elegida_id}`).
- `backend/app/presentation/api/v1/exam_content/catalog_router.py` — nuevo(s)
  endpoint(s) de armado aleatorio; endpoints de administración de categorías.
- Migraciones nuevas (tablas de categoría, blanks de cloze, posible columna
  `categoria_id`).

**Frontend:**
- Nueva pantalla de administración del banco de preguntas por categoría.
- `frontend/src/screens/Examen.tsx` / `ExamenPreguntaCard.tsx` — el frontend
  hoy ignora completamente el campo `tipo` de la pregunta; hace falta
  branching por tipo y un componente nuevo para cloze (enunciado con
  controles embebidos, no una lista de radios debajo).
- Estructura de "respuesta guardada" pasa de `{pregunta_id: opcion_id}` (un
  valor) a algo jerárquico para cloze (`{pregunta_id: {blank_id: valor}}`).

**Fuera de alcance de este change** (ver `10_preguntas_abiertas.md` / backlog):
auto-registro de alumnos vía link desde Moodle (LTI) — se investiga y propone
por separado, es un change de dominio CRITICAL (auth).
