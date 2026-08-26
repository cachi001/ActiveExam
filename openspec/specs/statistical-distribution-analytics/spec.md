# statistical-distribution-analytics Specification

## Purpose

Distribución estadística de scores por examen y detección de outliers como señal de priorización (NUNCA veredicto, RN-SC-01, DD-01), más métricas de calidad del detector como insumo de calibración en Fase 2 (RN-SC-05).
## Requirements
### Requirement: Distribución estadística de scores por examen
El sistema SHALL exponer la **distribución estadística** de los scores finales de un examen (histograma y/o percentiles), calculada sobre los datos consolidados de C-13.

#### Scenario: Distribución de scores de un examen
- **WHEN** se solicita la distribución estadística de un examen cerrado
- **THEN** el sistema devuelve el histograma/percentiles de los scores finales del examen a partir de los agregados consolidados

### Requirement: Detección de outliers como señal de priorización, nunca veredicto
El sistema SHALL identificar las sesiones **estadísticamente atípicas** (outliers) según un **criterio estadístico configurable** relativo a la distribución del examen; el outlier SHALL exponerse como **prioridad ordinal / señal de revisión humana** y NO SHALL emitir veredicto, sanción, acusación ni acción automática (RN-SC-01, RN-RV-07, RN-DSR-04, DD-01).

#### Scenario: Outlier marcado como señal, no como culpa
- **WHEN** una sesión se desvía estadísticamente del cuerpo de la distribución del examen
- **THEN** el sistema la marca como outlier (candidata a revisión humana prioritaria) sin emitir ningún veredicto, sanción ni acción automática sobre ella

#### Scenario: Criterio de outlier configurable y relativo a la distribución
- **WHEN** se configura el criterio estadístico de outlier (p. ej. percentil/desviación)
- **THEN** la identificación de atípicos se calcula relativa a la distribución del examen, no contra un umbral absoluto de culpa

### Requirement: Métricas de calidad del detector para calibración
El sistema SHALL computar **métricas agregadas de calidad del detector** (p. ej. la proporción de sesiones flaggeadas que el revisor humano descartó, proxy de falso positivo) leyendo las decisiones de C-16, y SHALL exponerlas como **insumo de análisis para calibración en Fase 2** sin disparar recalibración automática de umbrales (RN-SC-05).

#### Scenario: Tasa de falsos positivos descartados por el humano
- **WHEN** se solicita la métrica de calidad del detector de un período
- **THEN** el sistema reporta la proporción de sesiones flaggeadas que el revisor humano descartó, agregada, como insumo de calibración

#### Scenario: La métrica de calidad no recalibra umbrales automáticamente
- **WHEN** una métrica de calidad indica una tasa alta de falsos positivos
- **THEN** el sistema solo expone la métrica y no ajusta automáticamente ningún umbral de encolado (la recalibración es decisión humana/operativa)

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

