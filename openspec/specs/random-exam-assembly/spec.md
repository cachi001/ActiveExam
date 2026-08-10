# random-exam-assembly Specification

## Purpose
TBD - created by archiving change c-74-banco-preguntas-categorias-cloze. Update Purpose after archive.
## Requirements
### Requirement: Armado aleatorio de examen por categoría
El sistema SHALL ofrecer un endpoint `POST /exam-content/{examen_id}/sortear-preguntas` que recibe `{categoria_ids: list[str], cantidad_por_categoria: int}` y sortea, **una sola vez** server-side, esa cantidad de preguntas por cada categoría indicada. El payload SHALL admitir **varias** categorías a la vez (mezclar unidades en un mismo examen es el caso normal). El sorteo SHALL persistir de inmediato marcando `seleccionada = true` en las filas elegidas de `pregunta_examen`; NO SHALL existir un estado "sorteo calculado pero no guardado".

#### Scenario: Sortear preguntas de varias categorías queda persistido de inmediato
- **WHEN** un docente sortea 5 preguntas de la categoría A y 5 de la categoría B sobre un examen sin intentos
- **THEN** el sistema marca exactamente 10 preguntas `seleccionada = true`, repartidas 5/5, persistidas de inmediato

#### Scenario: Repetir el sorteo antes de rendir produce un resultado nuevo
- **WHEN** se vuelve a ejecutar el sorteo sobre el mismo examen antes de que haya un intento finalizado
- **THEN** el sistema produce una selección nueva (el sorteo no es idempotente: cada sorteo es un evento)

### Requirement: Validación de categoría y cantidad disponible
El sistema SHALL validar que cada `categoria_id` del sorteo pertenece a la materia del examen y SHALL rechazar con un error claro un `categoria_id` ajeno a esa materia. Si `cantidad_por_categoria` excede la cantidad de preguntas disponibles en una categoría, el sistema SHALL fallar con un error claro y NUNCA SHALL truncar en silencio.

#### Scenario: Categoría ajena a la materia del examen es rechazada
- **WHEN** el sorteo incluye un `categoria_id` que no pertenece a la materia del examen
- **THEN** el sistema rechaza la operación con un error claro y no marca ninguna pregunta

#### Scenario: Cantidad mayor a la disponible falla sin truncar
- **WHEN** `cantidad_por_categoria` es mayor a las preguntas disponibles en una de las categorías
- **THEN** el sistema responde con un error claro y no realiza un sorteo parcial ni truncado

### Requirement: Candado de congelamiento post-intento reusado
El sorteo SHALL reusar el mismo candado de congelamiento que la selección manual existente: si el examen ya tiene **al menos un intento finalizado**, el sistema SHALL responder `409` y NO SHALL alterar la selección. No SHALL existir un candado paralelo: sorteo y selección manual comparten el mismo mecanismo `_seleccion_bloqueada`.

#### Scenario: Sortear sobre un examen ya rendido devuelve 409
- **WHEN** se intenta sortear preguntas sobre un examen que ya tiene un intento finalizado
- **THEN** el sistema responde `409` y no modifica la selección de preguntas, igual que la selección manual

### Requirement: Frontend de armado por sorteo en la pantalla de examen
El sistema SHALL ofrecer, en la pantalla de examen (no en la pantalla del banco), una opción "Armar por sorteo" junto a la selección manual existente, con un selector de una o más categorías y la cantidad por categoría. Esta opción SHALL estar deshabilitada u oculta cuando el examen ya tiene un intento finalizado, con el mismo gate visual que ya aplica a la selección manual.

#### Scenario: El sorteo se ofrece junto a la selección manual y se bloquea al rendir
- **WHEN** un docente abre la pantalla de un examen sin intentos finalizados
- **THEN** ve la opción "Armar por sorteo" con selector de categorías y cantidad; si el examen ya tiene un intento finalizado, la opción aparece deshabilitada u oculta

