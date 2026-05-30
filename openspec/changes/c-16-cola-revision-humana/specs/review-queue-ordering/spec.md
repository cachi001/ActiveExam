# Spec — review-queue-ordering

> Cola de revisión ordenada por score descendente y filtrada por la jurisdicción del revisor (RN-RV-02, RN-AU-07, Flujo 7).

## ADDED Requirements

### Requirement: Cola ordenada por score descendente
La cola de revisión SHALL presentar las **sesiones flaggeadas** (las que superaron el umbral en C-13) ordenadas por **score descendente** (mayor primero) (RN-RV-02).

#### Scenario: Mayor score primero
- **WHEN** el revisor abre la cola con varias sesiones flaggeadas
- **THEN** las sesiones se presentan ordenadas por score descendente, la de mayor riesgo primero

### Requirement: Filtrado por jurisdicción del revisor
La cola SHALL mostrar **únicamente** las sesiones de la **jurisdicción** del revisor (RN-RV-01, RN-AU-07); las sesiones de otras jurisdicciones SHALL NOT ser visibles ni accesibles.

#### Scenario: Revisor ve solo su jurisdicción
- **WHEN** el revisor abre la cola
- **THEN** solo ve sesiones flaggeadas de su jurisdicción

#### Scenario: Acceso a sesión de otra jurisdicción rechazado
- **WHEN** el revisor intenta acceder a una sesión fuera de su jurisdicción
- **THEN** el acceso es rechazado
