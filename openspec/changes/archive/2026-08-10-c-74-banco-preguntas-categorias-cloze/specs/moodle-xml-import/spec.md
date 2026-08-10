# moodle-xml-import Specification

## MODIFIED Requirements

### Requirement: Importar Moodle XML al modelo de contenido
El sistema SHALL aceptar un documento "Moodle XML" subido por un admin y SHALL crear un examen de contenido con sus preguntas y opciones a partir de las preguntas soportadas del XML. Como mínimo SHALL soportar los tipos `multichoice`, `truefalse` y `cloze`/`multianswer`, mapeando el enunciado, las opciones y cuál es la correcta al modelo `exam-content-model`. Para las preguntas `cloze`/`multianswer` el sistema SHALL parsear la sintaxis embebida `{N:TIPO:...}` del `questiontext` (cubriendo como mínimo `MULTICHOICE` y `SHORTANSWER`) y persistirlas como preguntas con sus blanks y opciones según `cloze-question-type`, sin descartarlas como tipo no soportado.

#### Scenario: Importar un quiz Moodle con preguntas de opción múltiple
- **WHEN** un admin sube un export Moodle XML con preguntas `multichoice` válidas
- **THEN** el sistema crea un examen de contenido con esas preguntas y opciones, conservando server-side qué opción es la correcta

#### Scenario: Importar preguntas verdadero/falso
- **WHEN** el XML contiene preguntas `truefalse`
- **THEN** el sistema las importa como preguntas con exactamente dos opciones y la correcta marcada server-side

#### Scenario: Importar preguntas cloze con blanks embebidos
- **WHEN** el XML contiene preguntas `cloze`/`multianswer` con placeholders `{N:MULTICHOICE:...}` / `{N:SHORTANSWER:...}` en el `questiontext`
- **THEN** el sistema las importa como preguntas cloze con sus blanks y opciones, preservando los placeholders al limpiar el HTML, sin caer a "tipo no soportado"

### Requirement: Reporte de preguntas importadas y omitidas
La importación SHALL devolver un reporte que indique cuántas preguntas se importaron y cuáles se omitieron por ser de un tipo no soportado o por ser inválidas, sin abortar la importación completa cuando hay preguntas no soportadas. Los tipos `cloze`/`multianswer` YA NO SHALL contarse como no soportados; los tipos que siguen fuera de alcance (p. ej. `essay`, `matching`, `numerical` como pregunta completa) SHALL reportarse como omitidos con su tipo.

#### Scenario: XML con tipos no soportados se importa parcialmente con reporte
- **WHEN** el XML mezcla preguntas soportadas (`multichoice`/`truefalse`/`cloze`) con tipos no soportados (p. ej. `essay`, `matching`)
- **THEN** el sistema importa las soportadas y devuelve un reporte que lista las omitidas con su tipo, sin fallar la operación completa

#### Scenario: XML inválido o vacío
- **WHEN** se sube un documento que no es un Moodle XML parseable o no contiene preguntas soportadas
- **THEN** el sistema responde con un error claro (4xx) y no crea un examen de contenido vacío

## ADDED Requirements

### Requirement: El import clasifica las preguntas por categoría de Moodle
El import SHALL usar los nodos `<question type="category">` del XML (hoy descartados) para clasificar las preguntas en la jerarquía de `question-bank-categories`. El sistema SHALL trackear el nodo `category` activo durante el recorrido del XML (Moodle lo posiciona antes de las preguntas que le pertenecen, NO las anida), parsear su ruta (`$course$/top/Unidad 1/Subtema` → segmentos `["Unidad 1", "Subtema"]`, descartando el prefijo `$course$/top`), resolver-o-crear la jerarquía de `categoria_pregunta` por ruta y materia, y asignar la `categoria_id` resultante a cada pregunta que siga en el archivo. La resolución SHALL ser **idempotente por ruta + materia**: la misma ruta repetida NO SHALL crear categorías duplicadas.

#### Scenario: Las preguntas quedan clasificadas en su categoría de Moodle
- **WHEN** un admin importa un XML con nodos `category` de ruta jerárquica seguidos de preguntas
- **THEN** cada pregunta queda con la `categoria_id` de la categoría (creada/resuelta) que la precede en el archivo

#### Scenario: Reimportar el mismo XML no duplica categorías
- **WHEN** se importa dos veces el mismo XML con categorías anidadas
- **THEN** la segunda importación reutiliza las categorías existentes por ruta + materia y no crea duplicados

#### Scenario: Preguntas sin categoría precedente quedan sin clasificar
- **WHEN** el XML tiene preguntas antes del primer nodo `category`
- **THEN** esas preguntas quedan con `categoria_id = NULL` (bucket "Sin clasificar"), igual que las preguntas legacy
