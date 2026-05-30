# Design — C-20 `reportes-analytics`

> Design técnico de **Fase 2** de la capa de **reportes y analytics post-examen** (US-016, FR-15). Solo-lectura/agregación sobre datos consolidados (score final de C-13, decisiones humanas de C-16) vía CQRS-lite. **Principios rectores**: los reportes INFORMAN y AGREGAN, nunca emiten veredicto ni acción automática (RN-SC-01, DD-01); privacidad por diseño y minimización de PII (Ley 25.326).

## Context

Terminado un ciclo de exámenes, la institución necesita comprender lo ocurrido a nivel agregado: distribución de scores, sesiones outlier, calidad del detector, sumario del período. Esta información solo emerge en la **agregación post-examen** — el sistema en operación trabaja sesión a sesión. C-13 ya dejó el **score final** por sesión y los **continuous aggregates** de TimescaleDB; C-16 ya dejó las **decisiones humanas** (descartar/escalar/derivar) persistidas e inmutables. Este change **lee y agrega** esas fuentes; no recalcula nada.

**Constraint inviolable #1 (gobernanza)**: el nivel L2.5 (DD-01) prohíbe la sanción/acción automática. RN-SC-01: el score es prioridad, no veredicto. RN-RV-07: ninguna sanción es automática. RN-DSR-04: el derecho de oposición a decisiones automatizadas se cumple por arquitectura. En la capa de reporting el riesgo se desplaza: un **outlier estadístico** o un **agregado** podría *parecer* un veredicto. El diseño debe garantizar que un reporte **describe, jamás acusa**.

**Constraint inviolable #2 (privacidad por diseño, Ley 25.326)**: los reportes deben **minimizar PII** — agregaciones estadísticas por defecto, no reexponer datos personales innecesarios. Lo que puede mostrarse agregado no se muestra identificado. El acceso a un reporte **nominal** (por estudiante) es un **acceso a datos personales**: requiere RBAC contextual (jurisdicción) y queda **auditado**. Los exports respetan la misma minimización.

**Constraints técnicos** (de la KB):
- **RN-SC-04 / RN-SC-05**: el score final ya existe (C-13); la calibración con datos reales de los umbrales conservadores se hace **en Fase 2** — las **métricas de calidad del detector** son precisamente ese insumo.
- **`14` §Niveles de métricas**: nivel **1 (Negocio)** = distribución de score, profundidad de cola; nivel **2 (Aplicación)** = latencias/percentiles; nivel **3 (Infra)**. Los reportes de negocio (distribución, outliers, calidad) son nivel 1; este change los expone como reporte consultable, no solo como métrica de monitoreo.
- **`08` §Patrones (CQRS-lite)**: las lecturas salen de **agregados materializados** (continuous aggregates de C-13), no de recorrer la hypertable cruda.

**Decisión heredada (no se re-decide)**: el `score` final (C-13), las severidades de `Evento` (C-10), las decisiones terminales de revisión (C-16) y el RBAC contextual + audit log (C-06/C-05) vienen dados. Este change agrega **agregaciones de reporting** sobre esas estructuras.

**Stakeholders**: coordinador y dirección académica (consumen reportes/sumario/exports), revisor (usa outliers como priorización), DPO/legal (garantía de minimización de PII y no-veredicto), estudiante (NO recibe veredicto; un reporte nominal sobre él es un acceso auditado a sus datos).

## Goals / Non-Goals

**Goals:**
- Reporte **por examen** (distribución de scores, conteos por estado terminal, métricas agregadas del período) sobre datos consolidados.
- Reporte **por estudiante** con acceso **RBAC contextual** y **auditado** (acceso a datos personales).
- **Distribución estadística** + **detección de outliers** como **señal de priorización** (nunca veredicto).
- **Métricas de calidad del detector** (p. ej. tasa de falsos positivos descartados por el humano) para **calibración en Fase 2**.
- **Exports** (CSV/JSON) y **sumario institucional**, ambos con **minimización de PII**.
- Garantizar por diseño que ningún reporte/outlier/export **emite veredicto ni acción automática**.

**Non-Goals:**
- NO recalcular el score (eso es **C-13**; aquí se **lee** el score final consolidado).
- NO re-decidir ni emitir decisiones de revisión (eso es **C-16**; aquí se **reportan agregadas** las decisiones humanas).
- NO emitir veredicto, sanción, acusación ni acción automática (RN-SC-01, RN-RV-07, RN-DSR-04) — un outlier es señal, no juicio.
- NO reexponer PII innecesaria; sin export nominal sin permiso + audit (Ley 25.326).
- NO afinar/aplicar automáticamente nuevos umbrales (este change **provee el insumo** de calibración; la decisión de recalibrar es humana/operativa).
- NO implementar audio (FR-16), LMS (FR-17) ni multi-tenancy (FR-18) — son otras épicas de Fase 2/3.

## Decisions

### D1 — Reportes de solo-lectura sobre agregados consolidados (CQRS-lite)
**Decisión**: los reportes se construyen **leyendo** los **continuous aggregates** de C-13 y las decisiones persistidas de C-16; no recorren la hypertable cruda ni recalculan score.
**Por qué**: `08` §Patrones (CQRS-lite) + DD-05 — los agregados materializados ya existen y escalan; recalcular sobre eventos crudos sería costoso y duplicaría la lógica de C-13.
**Alternativa considerada**: recomputar distribuciones desde la hypertable en cada request → costo prohibitivo y riesgo de divergir del score canónico de C-13.

### D2 — El outlier es una SEÑAL de priorización, NUNCA un veredicto (gobernanza por diseño)
**Decisión**: la detección de outliers produce un **marcador estadístico ordinal** (la sesión se desvía del cuerpo de la distribución) que **prioriza** la atención humana; jamás una acusación, sanción ni acción automática. El contrato de salida documenta "outlier = candidato a mirar, no culpable".
**Por qué**: DD-01 (L2.5), RN-SC-01, RN-RV-07, RN-DSR-04 — el riesgo de la capa de reporting es que un agregado *parezca* un juicio; la garantía legal exige que no lo sea, por arquitectura.
**Alternativa considerada**: marcar outliers como "sesiones sospechosas/fraudulentas" → viola el axioma del sistema y el contrato de C-01; **descartada categóricamente**.

### D3 — Privacidad por diseño: agregados por defecto, nominal restringido y auditado
**Decisión**: todo reporte es **agregado/estadístico por defecto** (sin PII). El reporte **nominal** (por estudiante) requiere **RBAC contextual** (jurisdicción del solicitante, C-06) y **escribe en el audit log** el acceso a datos personales. Los exports nominales requieren el mismo gate.
**Por qué**: Ley 25.326 + privacidad por diseño — lo que se puede contar agregado no se muestra identificado; un reporte nominal es un acceso a datos personales y debe ser trazable.
**Alternativa considerada**: reportes nominales abiertos a cualquier rol con acceso al módulo → reexposición innecesaria de PII; viola minimización de datos.

### D4 — Métricas de calidad del detector como insumo de calibración (no acción automática)
**Decisión**: se computan métricas agregadas del detector — p. ej. **tasa de sesiones flaggeadas que el humano descartó** (proxy de falso positivo, RN-SC-05), distribución de score por estado terminal — y se **exponen para análisis**; **no** disparan recalibración automática de umbrales.
**Por qué**: RN-SC-05 — la calibración con datos reales es Fase 2 y es una **decisión humana/operativa**; el sistema provee la evidencia, no actúa solo (coherente con D2 y el axioma L2.5).
**Alternativa considerada**: auto-ajuste de umbrales según la métrica → acción automática que afecta encolado; viola el principio de no-automatismo en decisiones con efecto sobre personas.

### D5 — Distribución estadística vía agregación, outliers por umbral estadístico configurable
**Decisión**: la distribución de scores por examen se expone como **histograma/percentiles**; los outliers se identifican por un **criterio estadístico configurable** (p. ej. por encima de un percentil parametrizable o desviación respecto del cuerpo de la distribución), no por un umbral de culpa.
**Por qué**: US-016 CA-1 — el objetivo es **detectar atípicos** para priorizar; el criterio debe ser estadístico (relativo a la distribución del examen), no un veredicto absoluto.
**Alternativa considerada**: umbral absoluto fijo de "outlier" → no se adapta a la distribución real de cada examen; pierde sentido estadístico.

### D6 — Exports y sumario institucional minimizados y sin veredicto agregado
**Decisión**: exports (CSV/JSON) y sumario institucional son **agregados por defecto**; el sumario describe volumen, distribución global, tasa de revisión y decisiones humanas **agregadas**, **sin** emitir veredictos institucionales agregados. El export nominal pasa por el gate de D3.
**Por qué**: US-016 CA-2 + Ley 25.326 + RN-SC-01 — el sumario informa a dirección académica sin convertir agregados en sanciones colectivas ni filtrar PII.
**Alternativa considerada**: sumario con ranking nominal de estudiantes "de mayor riesgo" → reexposición de PII + apariencia de veredicto; **descartada**.

## Arquitectura de reporting

```
FUENTES CONSOLIDADAS (solo-lectura)
   ├─ score final por sesión + continuous aggregates      ← C-13
   ├─ decisiones humanas (descartar/escalar/derivar)       ← C-16
   └─ severidades de Evento, RBAC contextual, audit log    ← C-10/C-06/C-05
   │   (CQRS-lite: leer agregados materializados)          [D1]
   ▼
CAPA DE AGREGACIÓN DE REPORTES
   ├─ Reporte por examen     → distribución de scores, conteos por estado terminal   [agregado]
   ├─ Reporte por estudiante → línea de tiempo agregada    [NOMINAL → RBAC + audit]  [D3]
   ├─ Distribución + OUTLIERS → señal de priorización, criterio estadístico config.  [D2, D5]
   ├─ Calidad del detector    → tasa de falsos positivos descartados, etc. (Fase 2)  [D4]
   ├─ Exports (CSV/JSON)      → agregado por defecto; nominal con gate D3            [D6]
   └─ Sumario institucional   → volumen, distribución global, decisiones agregadas   [D6]
   │
   ⚠ EN NINGÚN CASO un reporte/outlier/métrica/export emite veredicto o acción       [D2 — inviolable]
   ⚠ PII MINIMIZADA por diseño: agregado por defecto; nominal restringido y auditado [D3 — Ley 25.326]
```

## Modelo de datos afectado

| Estructura | Qué hace este change | Origen |
|-----------|----------------------|--------|
| `Sesión.score` (final) + continuous aggregates | **lee** y agrega (distribución, outliers) — no recalcula | C-13 (existe) |
| Decisión de revisión (descartar/escalar/derivar) | **lee** y agrega (calidad del detector, conteos por estado) — no re-decide | C-16 (existe) |
| `Evento` (severidades) | **lee** agregado por severidad para reportes — no muta | C-10 (existe) |
| `Audit log` (append-only) | **escribe** el acceso a reportes nominales/exports nominales | C-05 (existe; aquí se usa para auditar acceso) |
| (sin tablas nuevas de dominio) | reportes derivados de lecturas; cacheables como vistas/materializaciones de reporting si hace falta | — |

## Risks / Trade-offs

- **[Un outlier estadístico o agregado se interpreta como acusación]** → Mitigación: D2 — outlier expuesto como **prioridad ordinal** documentada como no-veredicto; tests de contrato de salida (señal, no juicio); ningún path emite acción automática.
- **[Un export o reporte nominal filtra PII innecesaria]** → Mitigación: D3/D6 — agregado por defecto; nominal solo con RBAC contextual + audit; export minimizado; tests de minimización de PII.
- **[La métrica de calidad del detector se usa para auto-recalibrar umbrales]** → Trade-off **rechazado**: D4 — la métrica **informa**, la recalibración es decisión humana/operativa (RN-SC-05); ningún auto-ajuste.
- **[Reportes recorren la hypertable cruda y no escalan]** → Mitigación: D1 — solo-lectura sobre continuous aggregates de C-13 (CQRS-lite); materializaciones de reporting si la latencia lo exige.
- **[Outlier con criterio absoluto pierde sentido en exámenes de distinta distribución]** → Mitigación: D5 — criterio estadístico **relativo a la distribución del examen**, configurable.
- **[Datos insuficientes en Fase 2 temprana → reportes poco significativos]** → Trade-off **aceptado**: el change requiere producto estable y un ciclo real consolidado; los reportes ganan valor con volumen (esperado en Fase 2).

## Migration Plan

1. Definir las **lecturas/agregaciones de reporte** sobre los continuous aggregates de C-13 y las decisiones de C-16 (CQRS-lite, D1).
2. Implementar el **reporte por examen** (distribución de scores, conteos por estado terminal) — agregado, sin PII.
3. Implementar el **reporte por estudiante** con gate **RBAC contextual + audit** del acceso nominal (D3).
4. Implementar **distribución estadística + detección de outliers** con criterio estadístico configurable, como señal de priorización (D2, D5).
5. Implementar **métricas de calidad del detector** (tasa de falsos positivos descartados, etc.) como insumo de calibración Fase 2 — sin auto-ajuste (D4).
6. Implementar **exports** (CSV/JSON) y **sumario institucional** minimizados, sin veredicto agregado (D6).
7. Garantizar y testear que **ningún path** emite veredicto/acción automática y que la **PII se minimiza** (agregado por defecto; nominal restringido + auditado).
8. Instrumentar la **distribución de score** y la **calidad del detector** como métricas de negocio (`14` nivel 1).

**Rollback**: feature aislada de solo-lectura; deshabilitar el módulo de reportes no afecta scores, eventos ni decisiones (las fuentes son inmutables y propiedad de C-13/C-16). Sin migración destructiva.

## Open Questions

Cerradas por este change:
- ¿De dónde salen los datos del reporte? → continuous aggregates de C-13 + decisiones de C-16 (solo-lectura, D1).
- ¿Un outlier es una acusación? → **NO, jamás**; es señal de priorización (D2).
- ¿Los reportes exponen PII? → minimizada; agregado por defecto, nominal restringido y auditado (D3).
- ¿La métrica de calidad recalibra umbrales sola? → **NO**; informa la decisión humana (D4).

Fuera de alcance (otros changes / fases):
- Afinado/aplicación de nuevos umbrales con estos datos → decisión humana/operativa de Fase 2 (RN-SC-05).
- Análisis de audio (FR-16), integración LMS (FR-17), multi-tenancy (FR-18) → otras épicas de Fase 2/3.
- Cálculo del score y de las decisiones de revisión → **C-13** y **C-16** (insumos, no se re-implementan).
