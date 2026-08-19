## ADDED Requirements

### Requirement: Los conteos de inventario del catálogo excluyen los exámenes dados de baja
El sumario institucional SHALL contar como exámenes del catálogo únicamente aquellos con `eliminado_en` en NULL, tanto en el conteo global como en el acotado por los filtros de materia / comisión / examen. Las métricas de **actividad** (sesiones iniciadas, sesiones finalizadas, distribución de scores, desgloses por materia/comisión/día, top de eventos) SHALL seguir contando la actividad de exámenes dados de baja: esa actividad ocurrió y es un hecho histórico.

#### Scenario: Un examen dado de baja no cuenta como inventario
- **GIVEN** el catálogo tiene N exámenes activos y uno dado de baja
- **WHEN** se solicita el sumario institucional sin filtros
- **THEN** el total de exámenes reportado es N

#### Scenario: La actividad del examen dado de baja se conserva
- **GIVEN** un examen dado de baja con sesiones rendidas
- **WHEN** se solicita el sumario institucional
- **THEN** esas sesiones siguen contándose en el total de sesiones, en la distribución de scores y en los desgloses por materia y comisión

#### Scenario: El filtro por examen dado de baja sigue resolviendo su actividad
- **WHEN** se solicita el sumario filtrando por el id de un examen dado de baja
- **THEN** el conteo de inventario de exámenes es 0 y las métricas de actividad de ese examen se reportan normalmente

### Requirement: Denominador declarado de las métricas de sesiones del sumario
El sumario institucional SHALL excluir de todas sus métricas de sesiones las sesiones de diagnóstico (sin examen vinculado), y ese criterio SHALL ser el mismo que aplican la Cola de revisión y las tarjetas de las demás pantallas de administración, conforme a la definición única de la capacidad `stat-denominator-coherence`.

#### Scenario: Diagnóstico excluido del sumario
- **GIVEN** existen sesiones de diagnóstico sin examen vinculado
- **WHEN** se solicita el sumario institucional
- **THEN** esas sesiones no se cuentan en el total de sesiones, ni en las finalizadas, ni en la distribución de scores, ni en el conteo de sesiones en riesgo

#### Scenario: El sumario y la Cola de revisión coinciden en las sesiones en riesgo
- **GIVEN** el mismo umbral vivo y ningún filtro aplicado
- **WHEN** se comparan las sesiones en riesgo del sumario institucional con las que lista la Cola de revisión
- **THEN** ambos números coinciden

### Requirement: Los exports reflejan el mismo recorte que la pantalla
Los exports del sumario (PDF y Excel) SHALL calcularse con exactamente los mismos filtros y los mismos criterios de inventario y actividad que la vista en pantalla, de modo que un informe descargado no pueda contradecir lo que la persona estaba mirando.

#### Scenario: Export con filtro aplicado
- **WHEN** se descarga el export con un filtro de materia, comisión o examen aplicado
- **THEN** las cifras del archivo coinciden con las de la pantalla bajo el mismo filtro, y la cabecera del archivo declara el recorte aplicado

#### Scenario: Export tras dar de baja un examen
- **GIVEN** un examen fue dado de baja
- **WHEN** se descarga el export sin filtros
- **THEN** el conteo de exámenes del archivo excluye el dado de baja, igual que la pantalla
