# filtro-etiqueta-fiel Specification

## Purpose
TBD - created by archiving change c-78-coherencia-y-mejoras-relevamiento. Update Purpose after archive.
## Requirements
### Requirement: Un filtro hace lo que su etiqueta dice
Un control de filtro cuya etiqueta promete **incluir** un subconjunto ("mostrar X") SHALL devolver ese subconjunto **además** de lo que ya se veía, nunca reemplazarlo. Si el comportamiento deseado es restringir a ese subconjunto, la etiqueta SHALL decirlo explícitamente ("solo X").

#### Scenario: "Mostrar archivadas" incluye, no reemplaza
- **GIVEN** un examen con filas de resultado archivadas y no archivadas
- **WHEN** el usuario activa el control "Mostrar archivadas"
- **THEN** la tabla muestra las filas archivadas **y** las no archivadas

#### Scenario: Por defecto las archivadas quedan ocultas
- **WHEN** el usuario carga el panel de resultados sin tocar el control
- **THEN** solo se muestran las filas no archivadas

#### Scenario: El total acompaña al filtro
- **WHEN** el usuario activa "Mostrar archivadas"
- **THEN** el total de la paginación cuenta el conjunto completo mostrado, no solo el subconjunto anterior

### Requirement: Contrato tri-estado del filtro de archivadas
`GET /api/v1/exam-content/{examen_id}/resultados` SHALL aceptar el parámetro `archivado` con tres valores: `false` (default, solo filas no archivadas), `true` (solo filas archivadas) y `todas` (sin filtrar). Un valor no reconocido SHALL responder `422` con un error identificable, en lugar de degradar silenciosamente a un comportamiento por defecto.

#### Scenario: Valor "todas" no filtra
- **WHEN** se pide el listado con `archivado=todas`
- **THEN** la respuesta incluye filas archivadas y no archivadas, y `total` las cuenta a ambas

#### Scenario: Valor "true" restringe a archivadas
- **WHEN** se pide el listado con `archivado=true`
- **THEN** la respuesta incluye únicamente filas archivadas

#### Scenario: Valor inválido es rechazado
- **WHEN** se pide el listado con un valor de `archivado` fuera del conjunto permitido
- **THEN** la respuesta es `422` con un error identificable

### Requirement: El estado "hay filtros aplicados" considera todos los filtros
Una pantalla que derive un estado de "hay filtros activos" —para habilitar el botón de limpiar, o para elegir entre el mensaje de "sin resultados para este filtro" y el de "no hay datos cargados"— SHALL considerar **todos** los filtros que esa pantalla ofrece, no un subconjunto.

#### Scenario: Filtrar solo por comisión habilita limpiar
- **GIVEN** la pantalla de Exámenes ofrece filtros de búsqueda, materia y comisión
- **WHEN** el usuario aplica únicamente el filtro de comisión
- **THEN** la pantalla reconoce que hay filtros activos y ofrece limpiarlos

#### Scenario: Vacío por filtro no se confunde con base vacía
- **GIVEN** existen datos cargados en el sistema
- **WHEN** un filtro cualquiera de la pantalla deja el resultado vacío
- **THEN** el mensaje indica que ningún registro coincide con los filtros, no que no hay datos cargados

#### Scenario: Vacío real se reporta como vacío real
- **GIVEN** no hay ningún registro cargado y ningún filtro aplicado
- **WHEN** se carga la pantalla
- **THEN** el mensaje indica que todavía no hay datos cargados

### Requirement: Una acción de fila opera sobre la fila que la ofrece
Una acción ofrecida en el menú contextual de una fila SHALL operar sobre el registro de esa fila. Una acción que ignore el identificador de la fila y lleve a un destino genérico SHALL corregirse para apuntar al registro, o retirarse del menú de fila y ubicarse como acción de la pantalla.

#### Scenario: La acción de configurar un examen abre ese examen
- **WHEN** el usuario abre el menú de acciones de una fila de la lista de exámenes y elige la acción de configurar/vincular
- **THEN** el destino corresponde al examen de esa fila, no a una pantalla genérica

#### Scenario: Las acciones de fila son consistentes entre vistas
- **WHEN** se comparan las acciones de fila ofrecidas en la vista de escritorio y en la vista compacta de la misma lista
- **THEN** ambas ofrecen el mismo conjunto de acciones

