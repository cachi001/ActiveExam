# Spec — adr-approval-baseline

> Capacidad de **governance documental**. Congela la línea base de decisiones de arquitectura. Los "scenarios" son criterios de Done verificables sobre el acta de aprobación de los 19 ADRs.

## ADDED Requirements

### Requirement: Acta de aprobación de los 14 ADRs Tier 1 (DD-01…DD-14)
El proyecto SHALL contar con un acta formal que apruebe los 14 ADRs Tier 1 del discovery (**DD-01 a DD-14**), dejando cada decisión marcada como `Aprobado` y congelada como contrato técnico de las fases siguientes.

#### Scenario: Los 14 ADRs Tier 1 aprobados
- **WHEN** el equipo técnico y el patrocinador revisan los ADRs
- **THEN** existe un acta firmada que lista DD-01..DD-14 con estado `Aprobado` y fecha; ningún ADR Tier 1 queda pendiente

#### Scenario: Decisiones estructurales congeladas
- **WHEN** un change posterior consume una decisión (p. ej. L2.5, TimescaleDB, cadena de custodia WORM, Keycloak)
- **THEN** la decisión proviene del acta aprobada y no se renegocia sin un nuevo ADR

### Requirement: Aprobación de las 5 revisiones A4 (DD-15…DD-19)
El proyecto SHALL aprobar las cinco revisiones del análisis independiente A4 (**DD-15 a DD-19**) que ajustan el SAD original para el MVP: Postgres-como-cola (DD-15), SSE+backplane (DD-16), abstracción del motor de visión (DD-17), liveness escalonado (DD-18) y principio rector de escalado (DD-19).

#### Scenario: Las 5 revisiones A4 aprobadas
- **WHEN** se revisan las revisiones A4
- **THEN** el acta registra DD-15..DD-19 como `Aprobado`, incluyendo la sustitución de RabbitMQ+Celery por Postgres-como-cola y de WebSocket+sticky por SSE+backplane para el panel en el MVP

#### Scenario: Rutas de evolución documentadas, no retrabajo
- **WHEN** se aprueba una revisión A4 que simplifica el SAD original
- **THEN** el acta documenta la opción del SAD (RabbitMQ, WebSockets, Redis) como evolución a habilitar solo si una métrica de la PoC (C-03) lo exige

### Requirement: Línea base entregada al equipo técnico
La línea base de los 19 ADRs aprobados SHALL entregarse al equipo técnico como contrato de arquitectura que gobierna C-02 en adelante.

#### Scenario: Contrato técnico disponible
- **WHEN** arranca cualquier change de implementación
- **THEN** el equipo dispone del set de 19 ADRs aprobados como fuente de verdad de las decisiones de arquitectura
