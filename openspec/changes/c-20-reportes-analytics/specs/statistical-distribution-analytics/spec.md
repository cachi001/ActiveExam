# Spec — statistical-distribution-analytics

> Distribución estadística de scores por examen y detección de outliers como señal de priorización (NUNCA veredicto, RN-SC-01, DD-01), más métricas de calidad del detector como insumo de calibración en Fase 2 (RN-SC-05).

## ADDED Requirements

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
