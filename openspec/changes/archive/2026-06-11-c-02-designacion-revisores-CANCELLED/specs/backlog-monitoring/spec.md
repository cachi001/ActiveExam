# Spec — backlog-monitoring

> Capacidad de **governance / control operativo**. Los "scenarios" son criterios de Done verificables sobre un mecanismo de monitoreo definido, no comportamiento de software. La instrumentación técnica de la métrica se materializa en C-16/C-13; aquí se define el mecanismo de gobierno.

## ADDED Requirements

### Requirement: Mecanismo de monitoreo de backlog definido
El proyecto SHALL definir un mecanismo de monitoreo del backlog de revisión, dado que el backlog acumulado es la señal de que SU-03 está fallando (Flujo 7 §caso de error). El mecanismo define métrica, umbrales, responsable y cadencia, con independencia de su implementación técnica posterior.

#### Scenario: Métrica de backlog definida
- **WHEN** se revisa el mecanismo de monitoreo
- **THEN** define como métrica el tamaño de la cola de revisión y la antigüedad de la sesión más vieja sin resolver, segmentadas por jurisdicción

#### Scenario: Umbrales y escalado definidos
- **WHEN** se revisa el mecanismo
- **THEN** define umbrales (p. ej. verde/ámbar/rojo) contra un plazo objetivo de resolución, e identifica quién escala y a quién cuando se cruza el umbral rojo

### Requirement: Responsable del backlog asignado
El mecanismo SHALL asignar al coordinador operativo la responsabilidad del backlog y a la dirección académica la aprobación de las acciones de escalado en estado crítico.

#### Scenario: Responsable y aprobador del backlog
- **WHEN** se revisa el mecanismo
- **THEN** el coordinador operativo figura como responsable del monitoreo y la dirección académica como aprobador de las acciones en estado rojo

### Requirement: Plan de respuesta ante backlog crítico
El mecanismo SHALL incluir un plan de respuesta escalonado para cuando el backlog supere el umbral crítico (O-003 materializado): activación de suplentes/doble cobertura, re-priorización por score, palanca de ajuste del umbral de flagging, re-dimensionamiento y, en el extremo, gestión de expectativas con el patrocinador.

#### Scenario: Respuesta escalonada documentada
- **WHEN** se revisa el plan de respuesta
- **THEN** enumera acciones escalonadas (suplentes/doble cobertura, re-priorización, ajuste del umbral institucional de flagging, re-dimensionamiento, escalado al patrocinador) con su responsable

### Requirement: Cadencia de re-validación del capacity model
El mecanismo SHALL fijar una cadencia de re-validación del modelo de dimensionamiento con datos reales: al cierre del piloto y trimestralmente el primer año.

#### Scenario: Cadencia de re-validación fijada
- **WHEN** se revisa el mecanismo
- **THEN** establece la re-validación del modelo al cierre del piloto y de forma trimestral durante el primer año
