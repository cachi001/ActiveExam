# Spec — moodle-xml-import

> Ingesta del export "Moodle XML" (subido por el admin) hacia el modelo `exam-content-model`. Se eligió Moodle XML y NO la REST API de Moodle porque las Web Services del core de Moodle no exponen el contenido de las preguntas; el XML sí. Admin-only.

## ADDED Requirements

### Requirement: Importar Moodle XML al modelo de contenido
El sistema SHALL aceptar un documento "Moodle XML" subido por un admin y SHALL crear un examen de contenido con sus preguntas y opciones a partir de las preguntas soportadas del XML. Como mínimo SHALL soportar los tipos `multichoice` y `truefalse`, mapeando el enunciado, las opciones y cuál es la correcta al modelo `exam-content-model`.

#### Scenario: Importar un quiz Moodle con preguntas de opción múltiple
- **WHEN** un admin sube un export Moodle XML con preguntas `multichoice` válidas
- **THEN** el sistema crea un examen de contenido con esas preguntas y opciones, conservando server-side qué opción es la correcta

#### Scenario: Importar preguntas verdadero/falso
- **WHEN** el XML contiene preguntas `truefalse`
- **THEN** el sistema las importa como preguntas con exactamente dos opciones y la correcta marcada server-side

### Requirement: La importación es admin-only
La operación de importación SHALL estar restringida a usuarios con rol de administración de exámenes; un usuario sin ese rol SHALL recibir 403.

#### Scenario: Usuario no-admin no puede importar
- **WHEN** un usuario sin rol de administración de exámenes intenta importar un Moodle XML
- **THEN** el sistema responde 403 y no crea ningún examen de contenido

### Requirement: Reporte de preguntas importadas y omitidas
La importación SHALL devolver un reporte que indique cuántas preguntas se importaron y cuáles se omitieron por ser de un tipo no soportado o por ser inválidas, sin abortar la importación completa cuando hay preguntas no soportadas.

#### Scenario: XML con tipos no soportados se importa parcialmente con reporte
- **WHEN** el XML mezcla preguntas soportadas (`multichoice`/`truefalse`) con tipos no soportados (p. ej. `cloze`, `essay`)
- **THEN** el sistema importa las soportadas y devuelve un reporte que lista las omitidas con su tipo, sin fallar la operación completa

#### Scenario: XML inválido o vacío
- **WHEN** se sube un documento que no es un Moodle XML parseable o no contiene preguntas soportadas
- **THEN** el sistema responde con un error claro (4xx) y no crea un examen de contenido vacío

### Requirement: La REST API de Moodle queda fuera de alcance
Este change SHALL NOT implementar integración con la REST API / Web Services de Moodle (token, listar cursos/quizzes, devolver nota); la única vía de ingesta de contenido SHALL ser el archivo Moodle XML.

#### Scenario: La ingesta es por archivo, no por API de Moodle
- **WHEN** se quiere traer el banco de preguntas de Moodle
- **THEN** la única vía soportada es subir el export Moodle XML; no existe llamada a la REST API de Moodle en este change
