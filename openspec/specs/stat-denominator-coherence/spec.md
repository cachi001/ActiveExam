# stat-denominator-coherence Specification

## Purpose
TBD - created by archiving change c-78-coherencia-y-mejoras-relevamiento. Update Purpose after archive.
## Requirements
### Requirement: Definición única de "entra a la Cola de revisión"
Una sesión SHALL considerarse "en cola de revisión" si y solo si tiene un examen real vinculado (`examen_contenido_id` no nulo) **y** su score alcanza o supera el `umbral_cola_revision` vivo de la configuración del sistema. Toda pantalla, tarjeta o export que reporte esa métrica SHALL usar esta definición, sin excepciones ni variantes locales.

Las sesiones de diagnóstico (`modo='test'`, sin examen vinculado) NO SHALL contarse en esa métrica en ninguna pantalla, porque no entran a la Cola de revisión.

#### Scenario: El Panel de administración no cuenta diagnóstico en la cola
- **GIVEN** existen sesiones de diagnóstico sin examen vinculado cuyo score supera el umbral
- **WHEN** se carga el Panel de administración
- **THEN** esas sesiones no se cuentan en la tarjeta de cola de revisión

#### Scenario: La tarjeta del Panel coincide con la Cola de revisión
- **GIVEN** el mismo conjunto de sesiones y el mismo umbral vivo
- **WHEN** se comparan la tarjeta de cola del Panel de administración y la cantidad de personas en riesgo que lista la Cola de revisión
- **THEN** ambos números coinciden

#### Scenario: El agregado del Registro de sesiones no cuenta diagnóstico
- **GIVEN** el Registro de sesiones lista sesiones finalizadas incluyendo las de diagnóstico
- **WHEN** se calcula su agregado de sesiones sobre el umbral de riesgo
- **THEN** las sesiones de diagnóstico quedan excluidas del agregado, aunque sigan apareciendo en el listado

#### Scenario: El umbral es el vivo, no un valor fijo
- **WHEN** el administrador cambia el `umbral_cola_revision` en la configuración del sistema
- **THEN** las tarjetas de cola de todas las pantallas reflejan el umbral nuevo sin requerir cambios de código

### Requirement: Denominador declarado de las métricas de sesiones
Toda tarjeta que reporte una cantidad de sesiones SHALL declarar su denominador en el texto descriptivo de la tarjeta, de modo que dos pantallas con el mismo label y distinto alcance sean distinguibles sin leer el código. En particular, una tarjeta que cuente únicamente sesiones finalizadas SHALL decirlo, y una que cuente toda la actividad SHALL decirlo.

#### Scenario: Dos pantallas con la misma métrica y distinto alcance
- **GIVEN** el Panel de administración reporta sesiones de cualquier estado y el Registro de sesiones reporta solo finalizadas
- **WHEN** un usuario compara ambas tarjetas
- **THEN** el texto de cada tarjeta declara su alcance y la diferencia entre los números es explicable desde la propia pantalla

### Requirement: Vocabulario de métricas desde la fuente única
Toda `StatCard` de la superficie de administración SHALL obtener su label, ícono y tono del catálogo único de métricas (`statCatalog`), invocándolo en lugar de declarar esos valores en la pantalla. Solo el texto descriptivo de alcance (`sub`) puede especializarse por pantalla. Una métrica que no exista en el catálogo SHALL agregarse al catálogo antes de usarse.

#### Scenario: Ninguna pantalla hardcodea el vocabulario de una métrica
- **WHEN** se revisa cualquier `StatCard` de la superficie de administración
- **THEN** su label, ícono y tono provienen del catálogo de métricas, no de literales en la pantalla

#### Scenario: La misma métrica se ve igual en dos pantallas
- **GIVEN** dos pantallas reportan la métrica de sesiones sobre el umbral de riesgo
- **WHEN** se comparan sus tarjetas
- **THEN** ambas muestran el mismo label, el mismo ícono y el mismo tono

### Requirement: Vocabulario sin valores muertos ni roles inexistentes
Los mapas de etiquetas del frontend NO SHALL contener claves que el backend no pueda emitir, y la documentación de los endpoints (docstrings, comentarios de RBAC) NO SHALL nombrar roles que fueron eliminados del dominio. Un valor recibido que no esté en el mapa SHALL seguir cayendo al fallback legible existente, nunca a un valor interno crudo.

#### Scenario: Etiqueta muerta removida
- **GIVEN** el backend representa una sesión no revisada con un único valor centinela
- **WHEN** se inspecciona el mapa de etiquetas de estado de revisión del frontend
- **THEN** no contiene claves alternativas que el backend nunca emite

#### Scenario: Valor desconocido no se filtra crudo a la UI
- **WHEN** el backend emite un valor de estado o de tipo de evento que el mapa de etiquetas no conoce
- **THEN** la UI muestra el fallback legible, no el identificador interno sin transformar

#### Scenario: La documentación no nombra roles eliminados
- **WHEN** se leen los docstrings de RBAC de los endpoints de estadísticas y del catálogo de exámenes
- **THEN** solo mencionan roles y capacidades vigentes en el dominio

