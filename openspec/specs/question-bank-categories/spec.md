# question-bank-categories Specification

## Purpose
TBD - created by archiving change c-74-banco-preguntas-categorias-cloze. Update Purpose after archive.
## Requirements
### Requirement: Jerarquía de categorías del banco de preguntas por materia
El sistema SHALL persistir una jerarquía de **categorías del banco de preguntas** asociada a una materia, donde cada categoría tiene un `nombre`, pertenece a **exactamente una** materia y PUEDE tener una categoría padre (self-FK nullable), soportando anidamiento arbitrario por construcción. La migración SHALL ser **aditiva** (rama activeexam, no remodela tablas existentes): tabla nueva `categoria_pregunta` (id, `materia_id` FK ON DELETE CASCADE, nombre, `categoria_padre_id` nullable self-FK ON DELETE CASCADE, creada_en). Borrar una materia SHALL eliminar sus categorías; borrar una categoría con subcategorías SHALL eliminar en cascada su subárbol.

#### Scenario: Crear una categoría con padre y listar el árbol por materia
- **WHEN** se crea una categoría raíz para una materia y luego una subcategoría que la referencia como padre
- **THEN** ambas quedan persistidas y el árbol de categorías de esa materia se recupera con la relación padre→hijo, soportando anidamiento arbitrario

#### Scenario: Una categoría pertenece a exactamente una materia
- **WHEN** se intenta persistir una categoría sin materia asociada
- **THEN** el sistema rechaza la operación: toda categoría pertenece a exactamente una materia

### Requirement: Clasificación de preguntas por categoría sin romper exámenes existentes
El sistema SHALL asociar cada pregunta del banco a **como máximo una** categoría mediante una columna `categoria_id` nullable en `pregunta_examen` (FK a `categoria_pregunta` ON DELETE SET NULL). La migración SHALL ser **aditiva**: los exámenes ya importados SHALL seguir funcionando idénticos con `categoria_id = NULL`. Borrar una categoría NUNCA SHALL borrar las preguntas asociadas: éstas SHALL quedar con `categoria_id = NULL` ("Sin clasificar").

#### Scenario: Borrar una categoría con preguntas asociadas no borra las preguntas
- **WHEN** se borra una categoría que tiene preguntas asociadas
- **THEN** las preguntas NO se borran y quedan con `categoria_id = NULL` (bucket "Sin clasificar")

#### Scenario: Las preguntas legacy sin categoría quedan sin clasificar
- **WHEN** se consulta el banco de una materia con exámenes importados antes de existir categorías
- **THEN** esas preguntas aparecen agrupadas bajo el bucket implícito "Sin clasificar", sin migración de datos forzada

### Requirement: Bucket implícito "Sin clasificar"
El sistema SHALL exponer, por materia, un bucket fijo "Sin clasificar" que agrupa todas las preguntas con `categoria_id = NULL`. Este bucket NO SHALL ser eliminable ni renombrable: es una categoría implícita, no una fila de `categoria_pregunta`.

#### Scenario: El bucket "Sin clasificar" es visible y no editable
- **WHEN** se administra el banco de una materia que tiene preguntas sin categoría
- **THEN** el bucket "Sin clasificar" se muestra agrupando esas preguntas y no ofrece acciones de renombrar ni eliminar

### Requirement: Pantalla de administración del banco de preguntas
El sistema SHALL ofrecer una pantalla de administración del banco de preguntas (`/admin/banco-preguntas`) **separada** del flujo de creación/edición de examen. La pantalla SHALL permitir seleccionar una materia, navegar el árbol de categorías (expandible, anidamiento arbitrario), listar las preguntas de cada categoría (enunciado + tipo, sin exponer opciones ni la marca de correcta), realizar el CRUD de categorías (crear/renombrar/borrar) y mover una pregunta de una categoría a otra. La creación manual de preguntas una por una NO SHALL ser parte de esta pantalla (el banco se puebla por import).

#### Scenario: Navegar el árbol de categorías y listar preguntas de una categoría
- **WHEN** un admin selecciona una materia y expande una categoría del árbol
- **THEN** ve las preguntas de esa categoría (enunciado y tipo) sin que se expongan las opciones ni cuál es la correcta

#### Scenario: Mover una pregunta a otra categoría actualiza el árbol
- **WHEN** un admin mueve una pregunta de una categoría a otra
- **THEN** la pregunta queda con la nueva `categoria_id` y el árbol refleja el cambio sin recargar toda la pantalla

