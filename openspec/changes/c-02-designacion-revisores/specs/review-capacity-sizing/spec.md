# Spec — review-capacity-sizing

> Capacidad de **dimensionamiento organizacional**. Los "scenarios" son criterios de Done verificables sobre un modelo de dimensionamiento documentado, no comportamiento de software.

## ADDED Requirements

### Requirement: Modelo de dimensionamiento humano documentado
El proyecto SHALL contar con un modelo de dimensionamiento humano que estime la carga de revisión a partir de la tasa esperada de sesiones flaggeadas (**5–15%**, SU-03) aplicada al volumen objetivo (**1.000 concurrentes sostenido / ~2.100 pico**, SU-06), y que la traduzca a un número de revisores y coordinadores requeridos.

#### Scenario: Modelo deriva el número de revisores de variables explícitas
- **WHEN** la dirección académica y coordinación operativa elaboran el dimensionamiento
- **THEN** existe un documento que define las variables (volumen `V`, tasa de flagging `f`, tiempo medio de revisión `t_rev`, horas productivas `h`, plazo objetivo `SLA_rev`) y deriva de ellas el número de revisores y coordinadores, en lugar de fijar un número arbitrario

#### Scenario: Tasa de flagging 5–15% aplicada al volumen objetivo
- **WHEN** se revisa el modelo
- **THEN** usa la tasa de sesiones flaggeadas en el rango 5–15% sobre el volumen objetivo de 1.000 sostenido / ~2.100 pico, citando SU-03 y SU-06

### Requirement: Dimensionamiento de refuerzo clavado al pico
El modelo SHALL dimensionar la plantilla base contra el volumen sostenido (1.000 / 5%) y el **refuerzo, suplencia y doble cobertura contra el pico** (~2.100 / 15%), de modo que el equipo no colapse en el primer pico multi-examen.

#### Scenario: Plantilla base y refuerzo de pico diferenciados
- **WHEN** se revisa el modelo de dimensionamiento
- **THEN** distingue una plantilla base calculada al sostenido y un refuerzo/doble cobertura calculado al pico, e incluye un margen para ausencias y rotación

### Requirement: Dimensionamiento por jurisdicción
El modelo SHALL calcular la cobertura **por jurisdicción** (no solo en agregado), porque el acceso del revisor es contextual a su jurisdicción (RBAC, KB 03).

#### Scenario: Cada jurisdicción tiene cobertura calculada
- **WHEN** se revisa el dimensionamiento
- **THEN** ninguna jurisdicción queda sin revisores asignados aunque el total agregado sea suficiente

### Requirement: Modelo revisable con datos reales
El modelo SHALL declararse explícitamente como revisable, con un compromiso de re-validar sus supuestos (`f`, `t_rev`) con datos reales al cierre del piloto y trimestralmente el primer año (KB 15 §recomendación 3).

#### Scenario: Compromiso de re-validación registrado
- **WHEN** se revisa el modelo
- **THEN** incluye los valores de partida documentados como supuestos y un compromiso explícito de re-dimensionar tras el piloto y de forma trimestral el primer año
