# Spec — sustained-capacity-signoff

> Capacidad de **governance documental**. Los "scenarios" son criterios de Done verificables sobre una confirmación firmada, no comportamiento de software. Es el entregable terminal que cierra el gate C-02.

## ADDED Requirements

### Requirement: Confirmación por escrito de capacidad sostenida firmada
El proyecto SHALL contar con una confirmación por escrito, firmada por la dirección académica, de que el equipo de revisión designado y capacitado puede sostener la revisión del 5–15% de las sesiones al volumen objetivo (1.000 sostenido / ~2.100 pico) de forma continua, antes de cerrar Fase 0 (SU-03, O-003).

#### Scenario: Confirmación firmada por dirección académica
- **WHEN** se completan la designación, la capacitación y el dimensionamiento
- **THEN** existe un documento firmado por la dirección académica que confirma la capacidad sostenida del equipo de revisión, con fecha y versión registradas

#### Scenario: Capacidad sostenida, no solo de piloto
- **WHEN** se revisa la confirmación
- **THEN** declara explícitamente que la capacidad es sostenida en operación continua, no únicamente durante el piloto controlado

### Requirement: Confirmación referencia los entregables que la sustentan
La confirmación SHALL referenciar el modelo de dimensionamiento, la designación nominal por jurisdicción, la capacitación completada y el mecanismo de monitoreo de backlog, de modo que el sign-off sea trazable y no una declaración vacía.

#### Scenario: Sign-off trazable a sus entregables
- **WHEN** se revisa la confirmación firmada
- **THEN** referencia el modelo de dimensionamiento (`review-capacity-sizing`), la designación (`reviewer-designation`), la capacitación (`role-training-plan`) y el monitoreo (`backlog-monitoring`)

### Requirement: Gate de Fase 0 cerrado solo con la confirmación
El cierre de Fase 0 SHALL requerir esta confirmación firmada junto con los entregables de C-01, dado que C-02 es co-bloqueante: sin el equipo humano confirmado, C-16 no cumple su propósito aunque el código exista.

#### Scenario: Sin confirmación no se cierra Fase 0
- **WHEN** se evalúa el cierre de Fase 0
- **THEN** la ausencia de la confirmación firmada de capacidad sostenida impide marcar C-02 como completo y, por tanto, cerrar el gate organizacional de Fase 0
