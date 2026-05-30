# Proposal — C-20 `reportes-analytics`

> **Naturaleza del change**: feature de **Fase 2** (refinamiento), governance **MEDIO**, frontend + backend. Implementa los **reportes post-examen y analytics** (US-016, FR-15): reportes por examen y por estudiante, distribución estadística para detectar outliers, métricas de calidad del detector, exports y sumario institucional. **Principio inviolable (L2.5, RN-SC-01, DD-01)**: los reportes **INFORMAN y AGREGAN, NUNCA emiten veredicto ni acción automática**. **Depende de C-13** (score final) y **C-16** (decisiones humanas de revisión). Requiere un producto estable.

## Why

Tras un ciclo de exámenes, la institución (coordinación / dirección académica) necesita **entender qué pasó** a nivel agregado: ¿cómo se distribuyeron los scores de riesgo en este examen?, ¿hay sesiones outlier que el filtro humano debería mirar con prioridad?, ¿el detector está generando demasiados falsos positivos?, ¿cuál es el sumario institucional para el período? Esta información no existe mientras el sistema solo opera sesión a sesión: emerge **solo en la agregación post-examen**.

Hay dos motivaciones complementarias. **(1) Operativa**: detectar **outliers** (sesiones cuyo score se desvía estadísticamente del cuerpo de la distribución) ayuda a priorizar la revisión humana y a dimensionar el backlog (SU-03). **(2) De calibración**: las **métricas de calidad del detector** son el insumo para afinar los umbrales conservadores del MVP con datos reales — exactamente lo que RN-SC-05 difiere a Fase 2. Sin estos reportes, la calibración sería a ciegas.

El axioma del nivel L2.5 (DD-01, RN-SC-01) gobierna este change de punta a punta: un reporte **describe y agrega, jamás juzga**. Un outlier estadístico **NO es una acusación**: es una señal para que un humano mire. El sumario institucional **NO emite sanciones agregadas**. Confundir "score alto en el reporte" con "culpa" rompería la garantía legal del sistema (derecho de oposición a decisiones automatizadas, RN-DSR-04) y el contrato del Acuerdo de Nivel de Proctoring (C-01). Además, por **privacidad por diseño y Ley 25.326**, los reportes priorizan **agregaciones estadísticas** y **no reexponen PII innecesaria**: lo que se puede contar agregado no se muestra identificado.

Técnicamente, el sistema ya materializó los datos: C-13 dejó el **score final** por sesión (y los continuous aggregates de TimescaleDB), y C-16 dejó las **decisiones humanas** (descartar/escalar/derivar) persistidas e inmutables. Este change **lee y agrega** esas fuentes existentes (CQRS-lite, `08` §Patrones) — no recalcula scores ni re-decide nada.

## What Changes

Implementa la capa de reportes y analytics post-examen sobre datos ya consolidados:

- **Reporte por examen**: para un examen cerrado, agrega la **distribución de scores** (histograma/percentiles), el conteo de sesiones por estado terminal (archivada / flaggeada / revisada y su decisión humana), profundidad de cola y métricas agregadas del período. **Datos agregados, no nominales por defecto.**
- **Reporte por estudiante**: la **línea de tiempo agregada** de las sesiones de un estudiante (score final, eventos por severidad, decisiones humanas asociadas). Acceso **restringido por RBAC contextual** (jurisdicción del revisor/coordinador, C-06) y **auditado** — el acceso a un reporte nominal es un acceso a datos personales (Ley 25.326).
- **Distribución estadística + detección de outliers**: sobre la distribución de scores de un examen, identificar las sesiones **estadísticamente atípicas** (p. ej. > percentil configurable / desviación respecto del cuerpo de la distribución). El outlier es una **señal de priorización, no un veredicto** (RN-SC-01).
- **Métricas de calidad del detector**: agregados que miden el comportamiento del detector (p. ej. proporción de sesiones flaggeadas que el humano descartó como falso positivo, RN-SC-05) para **afinar umbrales con datos reales en Fase 2**. Métrica de negocio (`14` §Niveles de métricas, nivel 1).
- **Exports**: exportación de los reportes/agregados (CSV/JSON) para uso institucional; los exports **respetan la minimización de PII** (agregados por defecto; export nominal solo con permiso + audit).
- **Sumario institucional**: vista agregada del período (volumen de exámenes/sesiones, distribución global de scores, tasa de revisión, decisiones humanas agregadas) para dirección académica. **Sin veredictos agregados.**
- **Garantía de no-veredicto y privacidad por diseño**: ningún reporte, outlier, métrica o export emite sanción, acusación ni acción automática; las agregaciones priorizan estadística sobre identificación (Ley 25.326, RN-SC-01, RN-DSR-04).

**Decisiones consumidas (no se re-deciden aquí)**:
- El **score final** por sesión y los continuous aggregates de TimescaleDB vienen de **C-13**; este change los **lee y agrega**, no recalcula el score.
- Las **decisiones humanas de revisión** (descartar/escalar/derivar) y su trazabilidad vienen de **C-16**; este change las **reporta agregadas**, no las re-decide.
- El RBAC contextual y el audit log de acceso vienen de C-06/C-05; este change los **usa** para gobernar el acceso a reportes nominales.

**BREAKING**: ninguno. Change aditivo de solo-lectura sobre datos consolidados (no muta scores, eventos ni decisiones).

## Capabilities

> Cada SHALL se prueba con un test (agregaciones, exports, distribución estadística, detección de outliers, no-veredicto, minimización de PII).

### New Capabilities

- `post-exam-reports`: los reportes agregados por examen y por estudiante sobre datos consolidados (score final de C-13, decisiones humanas de C-16), con acceso a reportes nominales gobernado por RBAC contextual y auditado.
- `statistical-distribution-analytics`: la distribución estadística de scores por examen y la **detección de outliers** como señal de priorización (nunca veredicto), más las **métricas de calidad del detector** para calibración en Fase 2.
- `report-exports-and-summary`: los **exports** (CSV/JSON) y el **sumario institucional** del período, ambos respetando minimización de PII (agregados por defecto; nominal solo con permiso + audit) y sin emitir veredictos agregados.

### Modified Capabilities

<!-- Ninguna spec de dominio previa en openspec/specs/ se modifica. El score final (C-13) y las decisiones de revisión (C-16) son insumos de solo-lectura, no specs a redefinir aquí. -->

(Ninguna — este change agrega capacidades nuevas de solo-lectura/agregación; no modifica requisitos ya especificados en `openspec/specs/`.)

## Impact

- **Habilita**: la **calibración con datos reales** de los umbrales conservadores del MVP (RN-SC-05, Fase 2); la **visibilidad institucional** para coordinación/dirección académica; el dimensionamiento del equipo humano de revisión (SU-03, C-02) con datos de distribución reales.
- **Dependencias entrantes**: `C-13` (score final por sesión + continuous aggregates — la materia prima de la distribución) y `C-16` (decisiones humanas de revisión — la materia prima de las métricas de calidad del detector). Requiere un **producto estable**: sin un ciclo de exámenes real consolidado, no hay datos que agregar.
- **Decisiones que consume**: score final y agregados (C-13); decisiones terminales humanas (C-16); RBAC contextual + audit log de acceso (C-06/C-05).
- **Actores/sistemas afectados**: coordinador y dirección académica (consumidores de reportes/sumario), revisor (usa outliers como priorización), DPO/legal (garantía de minimización de PII y no-veredicto). El **estudiante NO recibe veredicto** de ningún reporte; un reporte nominal sobre él es un **acceso a datos personales auditado**.
- **Garantía de gobernanza**: refuerza por arquitectura el principio "ninguna sanción/acción automática" (RN-SC-01, RN-RV-07, RN-DSR-04) **en la capa de reporting** — el riesgo aquí es que un agregado "parezca" un veredicto; el diseño lo impide. Es **load-bearing** para el contrato de C-01.
- **Garantía de privacidad (Ley 25.326)**: privacidad por diseño en reporting — agregaciones estadísticas por defecto, no reexposición de PII innecesaria, acceso nominal restringido por RBAC y auditado, exports minimizados.
- **Riesgo principal**: que un outlier estadístico o un agregado se interprete (o se exponga) como acusación, o que un export filtre PII. Mitigación: outlier = señal ordinal documentada como no-veredicto; minimización de PII por defecto; acceso nominal gobernado y auditado.
