# Spec — reviewer-designation

> Capacidad de **governance organizacional**. Los "scenarios" son criterios de Done verificables sobre una designación nominal documentada, no comportamiento de software.

## ADDED Requirements

### Requirement: Revisores académicos designados nominalmente por jurisdicción
El proyecto SHALL designar de forma nominal a los revisores académicos requeridos por el modelo de dimensionamiento, asignados a su jurisdicción correspondiente, antes del inicio de Fase 1 (SU-03).

#### Scenario: Lista nominal de revisores por jurisdicción
- **WHEN** la dirección académica completa la designación
- **THEN** existe una lista nominal de revisores con su jurisdicción asignada, cuyo número satisface el dimensionamiento de `review-capacity-sizing`

#### Scenario: Ninguna jurisdicción sin revisor titular
- **WHEN** se revisa la designación
- **THEN** cada jurisdicción cubierta por el sistema tiene al menos un revisor titular designado

### Requirement: Coordinación operativa designada
El proyecto SHALL designar la coordinación operativa responsable de gestionar la cola/backlog, asignar y escalar a TI (rol Coordinador, KB 03 §RACI).

#### Scenario: Coordinador operativo nominado
- **WHEN** se revisa la designación
- **THEN** existe al menos un coordinador operativo nominado con su responsabilidad de gestión de cola y backlog declarada

### Requirement: Suplencia y doble cobertura para picos
La designación SHALL incluir suplentes y un esquema de doble cobertura para los picos, de modo que ausencias, vacaciones o rotación no dejen una jurisdicción descubierta.

#### Scenario: Suplentes designados
- **WHEN** se revisa la designación
- **THEN** existen suplentes designados y un esquema de doble cobertura para las ventanas de pico multi-examen

### Requirement: RACI de la decisión de revisión respetado
La designación SHALL reflejar el RACI de la decisión: revisor responsable de la revisión, coordinador aprobador/responsable de backlog, dirección académica responsable de la decisión disciplinaria terminal (el sistema nunca sanciona automáticamente, DD-01).

#### Scenario: Cadena de decisión humana documentada
- **WHEN** se revisa la designación
- **THEN** la cadena revisor → coordinador → dirección académica queda documentada y deja explícito que la decisión disciplinaria final es siempre humana
