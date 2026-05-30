# Tasks — C-20 `reportes-analytics`

> Implementa los reportes post-examen, la distribución estadística/outliers, las métricas de calidad del detector, los exports y el sumario institucional. **Principios inviolables**: los reportes INFORMAN y AGREGAN, nunca emiten veredicto/acción (RN-SC-01, DD-01); PII minimizada por diseño (Ley 25.326). El Done de cada tarea es un test verde.

## 1. Capa de lectura/agregación sobre datos consolidados (CQRS-lite)

- [ ] 1.1 Definir las lecturas de reporting sobre los **continuous aggregates** de C-13 y las decisiones de C-16 (solo-lectura, no recorrer la hypertable cruda); Done: test de lectura desde agregados consolidados
- [ ] 1.2 Garantizar que la capa de reporte **no muta** scores ni decisiones (solo lee); Done: test de invariancia (scores/decisiones inalterados tras generar reportes)

## 2. Reporte por examen y por estudiante (capability `post-exam-reports`)

- [ ] 2.1 Reporte **por examen**: distribución de scores + conteo de sesiones por estado terminal; Done: test de agregación por examen sobre datos consolidados
- [ ] 2.2 Confirmar que el reporte por examen es **agregado, sin PII** por defecto; Done: test de ausencia de PII en el reporte por examen
- [ ] 2.3 Reporte **por estudiante**: línea de tiempo agregada (score final, eventos por severidad, decisiones humanas); Done: test de reporte nominal por estudiante
- [ ] 2.4 Gate de acceso nominal: **RBAC contextual** (jurisdicción) + escritura en **audit log** del acceso a datos personales (Ley 25.326); Done: test acceso dentro de jurisdicción auditado / fuera de jurisdicción rechazado

## 3. Distribución estadística, outliers y calidad del detector (capability `statistical-distribution-analytics`)

- [ ] 3.1 Exponer la **distribución estadística** de scores por examen (histograma/percentiles); Done: test de distribución sobre agregados consolidados
- [ ] 3.2 **Detección de outliers** con criterio estadístico **configurable y relativo a la distribución** del examen; Done: test de identificación de atípicos por criterio configurable
- [ ] 3.3 Exponer el outlier como **prioridad ordinal / señal de revisión**, jamás veredicto; Done: test de contrato de salida (señal, no culpa)
- [ ] 3.4 **Métricas de calidad del detector** (tasa de flaggeadas descartadas por el humano, etc.) leyendo decisiones de C-16; Done: test de cálculo de la métrica de calidad
- [ ] 3.5 Confirmar que la métrica de calidad **NO** dispara recalibración automática de umbrales (RN-SC-05); Done: test de ausencia de auto-ajuste de umbrales

## 4. Exports y sumario institucional (capability `report-exports-and-summary`)

- [ ] 4.1 **Exports** (CSV/JSON) de reportes/agregados; Done: test de export de reporte agregado
- [ ] 4.2 Export **agregado sin PII** por defecto; export **nominal** solo con RBAC contextual + audit; Done: test export agregado sin PII / export nominal con permiso auditado / sin permiso rechazado
- [ ] 4.3 **Sumario institucional** del período (volumen, distribución global, tasa de revisión, decisiones agregadas); Done: test de sumario agregado del período
- [ ] 4.4 Confirmar que el sumario **no** emite veredictos ni rankings nominales de estudiantes; Done: test de ausencia de veredicto/ranking nominal en el sumario

## 5. Garantías transversales de gobernanza y privacidad

- [ ] 5.1 Verificar que **ningún path** de reporte/outlier/métrica/export emite sanción, veredicto ni acción automática (RN-SC-01, RN-RV-07, RN-DSR-04, DD-01); Done: test exhaustivo de no-veredicto/no-acción
- [ ] 5.2 Verificar la **minimización de PII** transversal: agregado por defecto, nominal restringido + auditado (Ley 25.326); Done: test transversal de minimización de PII

## 6. Observabilidad y cierre

- [ ] 6.1 Instrumentar la **distribución de score** y la **calidad del detector** como métricas de negocio (`14` §Niveles de métricas, nivel 1); Done: métricas visibles en Prometheus/Grafana
- [ ] 6.2 Documentar que los reportes son insumo de **calibración de umbrales en Fase 2** (RN-SC-05) — decisión humana, no automática; Done: contrato de calibración documentado
