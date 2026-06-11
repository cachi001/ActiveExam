# Proposal — C-05 `core-models`

> **Naturaleza del change**: modelo de datos del dominio, governance **CRÍTICO**. Define las **entidades centrales** y sus invariantes en la base de datos: el ciclo de vida de la sesión, la cadena de custodia naciente (audit log append-only con hash encadenado), y el motor de telemetría (Evento como hypertable TimescaleDB). Es la **columna vertebral de datos** sobre la que se construye todo el dominio. Un error aquí (un trigger que no rechaza mutaciones, un enum mal restringido, una hypertable sin compresión) se propaga a la defendibilidad de la evidencia y a la escala. Depende de C-04 (repo + Alembic + extensión TimescaleDB ya habilitada).

## Why

El proyecto necesita persistir el ciclo de vida de un examen proctorizado con dos exigencias no negociables que vienen del dominio (`04` Modelo de Datos):

1. **Defendibilidad de la cadena de custodia**: el audit log debe ser **append-only de verdad** — un trigger que rechaza `UPDATE`/`DELETE` a nivel de base, con cada entrada encadenada al hash de la anterior (`hash_prev`, "blockchain rudimentaria" validada a diario, `04` §Audit log). Si esto se implementa solo en la capa de aplicación, un insider o un bug lo rompe; el dominio exige la garantía en el motor.
2. **Escala de telemetría a 1.000 concurrentes / ~2.100 pico / ~5.000 inserts/s** (SU-06): un examen de 1 h produce 4–5 millones de filas. Eso no lo sostiene una tabla Postgres nativa; exige **TimescaleDB hypertable** con índices `(session_id, timestamp)` y `(exam_id, timestamp)`, **compresión** (7 días sin comprimir, >7 días comprimido ~10×) y **continuous aggregates** para que los paneles lean de agregados materializados y no del raw (DD-05, `04` §Evento, `08` §CQRS-lite).

Además, el ciclo de vida de la **Sesión** (entidad central) debe restringir su `estado` al enum del dominio (`iniciada / activa / finalizada / flaggeada / cerrada`, `04` §Sesión) a nivel de constraint, no de convención. Y los datos sensibles — **Embedding** (cifrado at-rest, eliminado al egreso) y **Consentimiento** (inmutable) — deben modelarse con sus invariantes desde el día uno, por privacidad por diseño (DD-13) y por la Ley 25.326 (Argentina), tratando el embedding como sensible por defecto (SU-08).

Este change convierte "tenemos la extensión TimescaleDB habilitada (C-04)" en "tenemos el modelo de datos del dominio con sus invariantes en el motor y los puertos de repositorio para operarlo".

## What Changes

- **Entidades transaccionales** (PostgreSQL): `Usuario` (provisionado JIT desde el IdP), `Examen` (parámetros, umbral de score, ventana, retención), `Sesión` (entidad central, `estado` restringido al enum `iniciada/activa/finalizada/flaggeada/cerrada`, `score`, clave de sesión, timestamps), `Asignación` (proctor↔examen, relación *—*), `Consentimiento` (**inmutable**: `versión_texto`, `timestamp`, `hash`), `Embedding` (vector **cifrado** at-rest, `versión`, eliminado al egreso), `Evidencia` (hashes y firmas de la cadena de custodia, `uri_bucket`), `Caso disciplinario` (estado, referencias, extiende retención por hold).
- **Audit log append-only**: tabla con **trigger que rechaza `UPDATE`/`DELETE`** y **hash encadenado** (`hash_prev` = hash de la entrada anterior), conforme a `04` §Audit log y `08` §Cadena de custodia (DD-07).
- **Evento como hypertable TimescaleDB**: esquema (`session_id`, `exam_id` denormalizado, `tipo`, `severidad`, timestamps cliente/backend, `payload` JSON, `firma` HMAC, `schema_version`); particionado por día; **índices** `(session_id, timestamp)` y `(exam_id, timestamp)`; **política de compresión** (chunks <7d sin comprimir, >7d comprimidos); **continuous aggregates base** (eventos por sesión por minuto, score por sesión, sesiones activas por examen, distribución por tipo — `04` §Evento).
- **Migración 002**: crea todas las tablas de dominio, la hypertable, el trigger del audit log, las políticas de compresión y los continuous aggregates (sobre la extensión que dejó C-04 en 001).
- **Repositorios genéricos (puertos)** por dominio: interfaces de repositorio en la capa `application`/`domain` con adaptadores en `infrastructure/persistence`, manteniendo el dominio puro (Hexagonal, `08` §Patrones).
- **Tests**: constraints de enum de Sesión, el trigger append-only **rechaza** `UPDATE`/`DELETE`, el **encadenamiento de hash** es correcto, y la **hypertable se crea** con sus índices/compresión.

## Capabilities

> Estas capabilities modelan el **modelo de datos del dominio y sus invariantes en el motor**. Su Done es: la migración 002 crea las entidades, el trigger rechaza mutaciones, el hash encadena y la hypertable existe con su política de compresión y agregados.

### New Capabilities

- `domain-entities`: las entidades transaccionales (Usuario, Examen, Sesión, Asignación, Consentimiento, Embedding, Evidencia, Caso disciplinario) con sus atributos, cardinalidades e invariantes (`04`).
- `session-lifecycle-enum`: el `estado` de la Sesión restringido al enum `iniciada/activa/finalizada/flaggeada/cerrada` a nivel de constraint de base.
- `append-only-audit-log`: el audit log con trigger que rechaza `UPDATE`/`DELETE` y hash encadenado (`hash_prev`), base de la cadena de custodia (DD-07).
- `event-hypertable`: el Evento como hypertable TimescaleDB con índices `(session_id, timestamp)` y `(exam_id, timestamp)`, compresión (7d/>7d) y continuous aggregates base (DD-05).
- `domain-repositories`: los repositorios genéricos (puertos) por dominio con adaptadores en `infrastructure/persistence`, manteniendo el dominio puro.

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. -->

(Ninguna — este change crea el modelo de datos del dominio; no modifica requisitos previos.)

## Impact

- **Dependencias entrantes**: **C-04** (repo por capas, Alembic configurado y migración 001 con la extensión TimescaleDB ya habilitada). Sin la extensión presente, la hypertable de Evento no se crea.
- **Bloquea**: **C-06** (auth/RBAC — necesita la entidad `Usuario` para el JIT provisioning) y, por transitividad, todos los changes de dominio que operan sobre Sesión/Evento/Evidencia (ingesta, scoring, evidencia, revisión).
- **Decisiones que consume**: la convención de migraciones destructivas en dos pasos y la estructura de capas de C-04; el cifrado at-rest (KMS) definido en `08` §Seguridad para Embedding/Evidencia.
- **Decisiones que produce** (consumidas downstream): el esquema de Evento (que C-10 versiona y valida con firma HMAC de producción), el contrato del audit log (que toda operación auditada usa), y los puertos de repositorio que la capa de aplicación inyecta.
- **Actores/sistemas afectados**: desarrolladores de dominio (construyen sobre estas entidades), auditor (lee el audit log inmutable), DPO (Embedding/Consentimiento bajo Ley 25.326). No hay UI todavía.
- **Riesgo principal**: que el trigger append-only o el encadenamiento de hash tengan un hueco (mutación posible, hash no validable) — rompería la defendibilidad de la evidencia. Mitigado por tests que **intentan** mutar y verifican el rechazo, y que validan la cadena de hash extremo a extremo.
