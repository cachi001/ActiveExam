# Spec — job-queue-validation (Concern a)

> Capacidad de **validación de carga** del **Concern (a) — cola de trabajos asíncrona** (re-inferencia + firma de evidencia). Camino **asíncrono**, presupuesto **< 30 s**, NO tiempo real. Hipótesis default = Postgres-como-cola (A4, DD-15, IN-01).

## ADDED Requirements

### Requirement: Re-inferencia + firma final bajo 30 s al pico
La cola de trabajos SHALL completar el ciclo re-inferencia + firma final en **p99 < 30 s desde la subida** del clip, medido al pico (P2: ~2.100 conc. / ~5.000 inserts/s), tanto para la opción default (Postgres-como-cola con `SKIP LOCKED` + pg-boss) como para la alternativa del SAD (RabbitMQ quorum + Celery).

#### Scenario: Postgres-como-cola sostiene el presupuesto al pico
- **WHEN** se ejecuta P2 con la cola implementada en Postgres (`SKIP LOCKED` + pg-boss/`LISTEN/NOTIFY`)
- **THEN** la latencia re-inferencia+firma medida en Prometheus es p99 < 30 s y la profundidad de la cola se mantiene acotada (no crece sin techo)

#### Scenario: Comparación apples-to-apples contra RabbitMQ
- **WHEN** se ejecuta el mismo perfil P2 con la cola implementada en RabbitMQ quorum + Celery
- **THEN** se registra la misma métrica (p99 de re-inferencia+firma y profundidad de cola) bajo idéntico tráfico para comparar contra la opción Postgres

### Requirement: Veredicto del concern (a) por métrica, default conservado por omisión
El concern (a) SHALL conservar Postgres-como-cola (A4) por omisión y promover RabbitMQ+Celery (SAD) **solo si** la métrica al pico lo exige (p99 ≥ 30 s o profundidad de cola creciendo sin techo), documentándolo como evolución condicionada y no como retrabajo (DD-19).

#### Scenario: Conservar Postgres si sostiene
- **WHEN** Postgres-como-cola sostiene p99 < 30 s con cola estable al pico
- **THEN** el veredicto registra "conservar Postgres-como-cola (A4) ✓" con la métrica que lo justifica

#### Scenario: Promover RabbitMQ solo si la métrica lo exige
- **WHEN** Postgres-como-cola supera 30 s o su cola crece sin techo al pico, y RabbitMQ+Celery sí sostiene el presupuesto
- **THEN** el veredicto registra "promover RabbitMQ+Celery ✗" como evolución condicionada documentada en el ADR
