# review-queueing-decision Specification

## Purpose
TBD - created by archiving change c-13-scoring-incremental. Update Purpose after archive.
## Requirements
### Requirement: Encolado por umbral institucional configurable
Tras calcular el score final, si `score_final > umbral_institucional` la sesión SHALL pasar a estado **flaggeada** y entrar a la cola de revisión; en caso contrario SHALL **archivarse** (RN-SC-04). El umbral SHALL ser configurable por examen.

#### Scenario: Score sobre umbral encola la sesión
- **WHEN** el score final de una sesión supera el umbral institucional configurado para su examen
- **THEN** la sesión pasa a estado flaggeada y queda disponible en la cola de revisión

#### Scenario: Score bajo umbral archiva la sesión
- **WHEN** el score final de una sesión no supera el umbral
- **THEN** la sesión se archiva y no entra a la cola de revisión

### Requirement: El score PRIORIZA, nunca emite veredicto ni sanción
El score y la decisión de encolado SHALL producir únicamente una **prioridad** (orden de revisión) y un estado de sesión (flaggeada/archivada); el sistema SHALL NOT emitir ninguna sanción, culpa ni decisión disciplinaria automática (RN-SC-01, RN-RV-07, RN-DSR-04). La decisión terminal es siempre humana.

#### Scenario: Encolar no es sancionar
- **WHEN** una sesión se marca como flaggeada por superar el umbral
- **THEN** no se emite ninguna sanción ni decisión disciplinaria automática; la sesión solo queda priorizada para revisión humana

#### Scenario: Ningún path automático produce veredicto
- **WHEN** se recorre cualquier camino del cálculo de score y de la decisión de encolado
- **THEN** ningún path produce una decisión disciplinaria; la única salida es priorización (orden) o archivado

