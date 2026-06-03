## ADDED Requirements

### Requirement: Agregación pura de sesiones por catálogo académico

El sistema SHALL proveer un módulo `screens/proctoring/colaAgregacion.ts` con funciones puras (sin React, sin hooks, sin llamadas HTTP) que enriquecen y agrupan las sesiones de proctoring por la jerarquía del catálogo (materia → comisión → examen) usando `joinExamInfo`. SHALL exponer: `enriquecerYFiltrar(sesiones, umbral)`, `materiasEnRiesgo(items)`, `comisionesEnRiesgo(items, materia)`, `examenesEnRiesgo(items, materia, comision)` y `personasEnRiesgo(items, materia, comision, examen)`. Cada nodo de nivel SHALL incluir un contador `enRiesgo`.

#### Scenario: Enriquecer y filtrar por umbral
- **WHEN** se llama `enriquecerYFiltrar(sesiones, 60)`
- **THEN** retorna solo las sesiones con `score >= 60`, cada una con su `ExamInfo` (o null), ordenadas por score descendente

#### Scenario: Agrupar materias con contador
- **WHEN** se llama `materiasEnRiesgo(items)` sobre sesiones enriquecidas
- **THEN** retorna un nodo por materia con el conteo de sesiones en riesgo, ordenado por contador descendente

#### Scenario: Sesión sin info cae en sentinela
- **WHEN** una sesión enriquecida tiene `info` null
- **THEN** queda agrupada bajo el nodo "Sin examen asociado" en cada nivel de la agregación

#### Scenario: Personas de un examen
- **WHEN** se llama `personasEnRiesgo(items, materia, comision, examen)`
- **THEN** retorna las sesiones enriquecidas cuyo contexto académico coincide con esa materia, comisión y examen
