# Spec — role-training-plan

> Capacidad de **capacitación / gestión del cambio**. Los "scenarios" son criterios de Done verificables sobre un plan de capacitación ejecutado, no comportamiento de software.

## ADDED Requirements

### Requirement: Plan de capacitación por rol definido y ejecutado
El proyecto SHALL definir y ejecutar un plan de capacitación con una currícula por rol —proctor en vivo, revisor académico, coordinador operativo, on-call/TI— antes del inicio de Fase 1 (KB 15 §Gestión del cambio, SU-03).

#### Scenario: Currícula por cada rol
- **WHEN** se revisa el plan de capacitación
- **THEN** existe una currícula diferenciada para proctor, revisor, coordinador y on-call/TI, cada una con objetivos de aprendizaje declarados

#### Scenario: Capacitación completada y verificada
- **WHEN** finaliza la capacitación
- **THEN** existe registro de que cada persona designada completó su currícula con una evaluación verificable (caso práctico aprobado, no solo asistencia)

### Requirement: Currícula del revisor cubre el criterio de decisión
La currícula del revisor académico SHALL cubrir las tres decisiones terminales (descartar / escalar / derivar a disciplina), la lectura del contexto completo (línea de tiempo, clips firmados, re-inferencia, observaciones del proctor) y la gestión de falsos positivos (Flujo 7, US-012).

#### Scenario: Decisiones terminales y contexto en la currícula
- **WHEN** se revisa la currícula del revisor
- **THEN** incluye las tres decisiones terminales, la lectura del contexto completo de la sesión y el manejo de falsos positivos

### Requirement: Capacitación en restricciones de acceso y privacidad
La capacitación SHALL cubrir las restricciones de acceso heredadas del RBAC: **MFA obligatorio**, acceso a evidencia **auditado con propósito declarado**, jurisdicción contextual y los límites del sistema (sin sanción automática, sin video continuo, sin lockdown).

#### Scenario: Propósito declarado y MFA enseñados
- **WHEN** se revisa la capacitación
- **THEN** los revisores y coordinadores son instruidos en que cada apertura de evidencia se audita con propósito declarado, en el uso de MFA y en los límites deliberados del sistema

### Requirement: Capacitación de on-call vinculada a resiliencia operacional
La capacitación de on-call/TI SHALL incluir runbooks, simulacros y doble cobertura en picos, atendiendo también el riesgo O-001 (on-call insuficientemente capacitado).

#### Scenario: On-call con simulacros y doble cobertura
- **WHEN** se revisa la currícula de on-call
- **THEN** incluye runbooks, al menos un simulacro y el esquema de doble cobertura para ventanas críticas
