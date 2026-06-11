# Proposal — C-13 `scoring-incremental`

> **Naturaleza del change**: feature de producción, governance **ALTO**, backend auxiliar. Implementa el **score de riesgo incremental** (US-010, FR-10, Flujo 6) vía continuous aggregates de TimescaleDB. **Principio inviolable (L2.5, RN-SC-01, DD-01)**: el score **PRIORIZA, NO emite veredicto**. El sistema **NUNCA sanciona automáticamente** — la decisión es siempre humana. **Depende de C-10** (eventos en TimescaleDB).

## Why

El sistema produce, por examen de ~700 estudiantes, millones de eventos (`14`). Un revisor humano no puede mirar todas las sesiones: solo el 5–15% requiere revisión (RN-RV-01, SU-03). El score de riesgo existe para **ordenar la cola de revisión por prioridad**, no para juzgar: es el mecanismo que pone primero las sesiones más sospechosas frente a un revisor con tiempo finito.

El axioma del nivel L2.5 (DD-01) es categórico: **ninguna sanción es automática** (RN-SC-01, RN-RV-07, RN-DSR-04). El score es una **prioridad para la cola, no un veredicto**. Confundir score con culpa rompería la garantía legal del sistema (derecho de oposición a decisiones automatizadas, RN-DSR-04) y el contrato del Acuerdo de Nivel de Proctoring (C-01). Por eso este change **calcula y ordena, pero jamás decide**: la decisión terminal es de C-16 (revisor humano).

Técnicamente, calcular el score recorriendo todos los eventos al cierre sería costoso y lento. TimescaleDB ofrece **continuous aggregates** que materializan el agregado incrementalmente (al minuto) — el patrón CQRS-lite del proyecto (`08` §Patrones, DD-05). El score se acumula en vivo durante el examen y se consolida al cierre con una tarea asíncrona.

## What Changes

Implementa el cálculo de score incremental y la decisión de encolado por umbral (Flujo 6):

- **Score incremental** vía **continuous aggregate de TimescaleDB** (al minuto): pondera cada evento por **severidad, frecuencia y persistencia** (RN-SC-02). Un patrón sostenido pesa más que un pico aislado; **eventos correlacionados** (p. ej. mirada desviada + pérdida de foco simultáneas) **pesan más que la suma de sus partes** (RN-SC-03).
- **Cierre de sesión** (`POST /sessions/{id}/finish`): una **tarea asíncrona** consolida las métricas y calcula el **score final** (RN-SC-04); **libera la clave de sesión** rotativa.
- **Decisión de encolado por umbral**: si `score_final > umbral_institucional` → la sesión pasa a estado **flaggeada** y entra a la cola de revisión (consumida por C-16); si no → la sesión se **archiva**.
- **Garantía de no-veredicto**: el score **prioriza**, no sanciona. El sistema no emite ninguna decisión disciplinaria automática (RN-SC-01, RN-RV-07).
- **Calibración conservadora** (RN-SC-05): los umbrales del MVP minimizan falsos positivos en la detección automática (el filtro humano recupera los verdaderos positivos); se afinan con datos reales en Fase 2.

**Decisiones consumidas (no se re-deciden aquí)**:
- El esquema y la persistencia del `Evento` en TimescaleDB vienen de C-05/C-10; este change agrega los **continuous aggregates** de score sobre la hypertable existente.
- El estado `flaggeada` del enum de `Sesión` (de C-05) se usa, no se redefine.

**BREAKING**: ninguno. Habilita la cola de revisión: **C-16 consume** las sesiones flaggeadas y el orden por score que produce este change.

## Capabilities

> Cada SHALL se prueba con un test (agregado incremental, correlación, decisión de encolado por umbral, archivado, no-veredicto).

### New Capabilities

- `incremental-risk-score`: el score incremental vía continuous aggregate de TimescaleDB (al minuto) que pondera severidad, frecuencia y persistencia, con eventos correlacionados pesando más que la suma.
- `session-finalization`: el cierre de sesión (`/sessions/{id}/finish`) que consolida métricas vía tarea asíncrona, calcula el score final y libera la clave de sesión.
- `review-queueing-decision`: la decisión por umbral — score final > umbral → sesión flaggeada a la cola de revisión; si no → archivada — garantizando que el score **prioriza y nunca sanciona**.

### Modified Capabilities

<!-- Ninguna spec de dominio previa en openspec/specs/. El Evento (hypertable) y el enum de estado de Sesión provienen de C-05/C-10 como dependencia de implementación, no como spec a modificar aquí. -->

(Ninguna — este change agrega capacidades nuevas; no modifica requisitos ya especificados en `openspec/specs/`.)

## Impact

- **Habilita**: C-16 (`cola-revision-humana`) — consume las sesiones flaggeadas y el orden por score descendente que produce este change; cierra el ciclo MVP. También insumo de C-20 (reportes, Fase 2).
- **Dependencias entrantes**: `C-10` (eventos firmados persistidos en TimescaleDB — la materia prima del score) y, transitivamente, C-05 (hypertable `Evento`, enum de estado de `Sesión`).
- **Decisiones que consume**: esquema de `Evento` y severidades (RN-EV-04) de C-10; estado `flaggeada` de `Sesión` de C-05.
- **Actores/sistemas afectados**: TimescaleDB (continuous aggregates), tarea asíncrona de cierre, revisor (downstream, recibe la cola priorizada vía C-16). El estudiante **no recibe veredicto alguno** del score.
- **Garantía de gobernanza**: refuerza por arquitectura el principio "ninguna sanción automática" (RN-SC-01, RN-RV-07, RN-DSR-04); el score es priorización, no juicio. Esto es **load-bearing** para el contrato de C-01.
- **Riesgo principal**: calibrar el score demasiado agresivo generaría falsos positivos que saturan la cola humana (SU-03). Mitigación: calibración conservadora por defecto (RN-SC-05), afinada con datos reales en Fase 2.
