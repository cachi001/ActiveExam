# Design — C-05 `core-models`

> Design técnico del **modelo de datos del dominio**: entidades transaccionales, ciclo de vida de la sesión, audit log append-only con hash encadenado, y Evento como hypertable TimescaleDB. Establece las invariantes en el motor (no solo en la aplicación). Depende de C-04.

## Context

Modelo de datos de la KB (`04`): PostgreSQL con dos roles — **tablas transaccionales** para entidades de dominio y **TimescaleDB hypertable** para el Evento (series temporales). NFR de capacidad (SU-06): **1.000 sostenido / ~2.100 pico / ~5.000 inserts/s**; un examen de 1 h ⇒ 4–5M filas ⇒ ~100–200 MB con compresión. Decisiones aplicables: **DD-05** (TimescaleDB para eventos — conservar), **DD-07** (cadena de custodia con audit log inmutable y firmas encadenadas), **DD-13** (privacidad por diseño), **SU-08** (embedding sensible por defecto). Arquitectura por capas Hexagonal (`08` §Patrones): dominio puro, repositorios como puertos.

**Constraints**:
- El audit log debe ser **append-only a nivel de motor** (trigger), no solo de aplicación (`04` §Audit log; DD-07).
- Cada entrada del audit log incluye el **hash de la anterior** (`hash_prev`): cadena validable a diario.
- El `estado` de Sesión está **restringido al enum** del ciclo de vida a nivel de constraint.
- El Embedding es **cifrado at-rest** (KMS) y **se elimina al egreso** del estudiante; sensible por defecto (SU-08, Ley 25.326).
- El Consentimiento es **inmutable** (registro de acuse con hash).
- La hypertable de Evento requiere la **extensión TimescaleDB ya habilitada por C-04** (migración 001).
- Índices obligatorios del Evento: `(session_id, timestamp)` y `(exam_id, timestamp)`; compresión 7d/>7d; continuous aggregates base (`04` §Evento).

## Goals / Non-Goals

**Goals:**
- Modelar las 8 entidades de dominio con atributos, cardinalidades e invariantes (`04`).
- Restringir el `estado` de Sesión al enum a nivel de constraint.
- Implementar el audit log append-only con trigger anti-mutación y hash encadenado (`hash_prev`).
- Crear el Evento como hypertable con índices, compresión y continuous aggregates base.
- Entregar la migración 002 que materializa todo lo anterior.
- Exponer repositorios genéricos (puertos) por dominio, con dominio puro.

**Non-Goals:**
- NO implementar la lógica de scoring incremental ni las reglas de transición de eventos (changes de dominio posteriores).
- NO implementar la validación de firma HMAC de producción del Evento ni el esquema versionado definitivo (eso es C-10).
- NO implementar la firma maestra de evidencia, el bucket WORM ni la re-inferencia (changes de evidencia).
- NO implementar auth/RBAC sobre las entidades (eso es C-06) — solo la entidad `Usuario` y sus relaciones.
- NO implementar el cifrado/KMS de extremo a extremo: se modela el campo cifrado y su contrato; la rotación de claves la opera infraestructura (`08`).

## Decisions

### D1 — Audit log append-only en el motor: trigger que rechaza UPDATE/DELETE
**Decisión**: la tabla `audit_log` lleva un **trigger BEFORE UPDATE/DELETE** que aborta la operación (`RAISE EXCEPTION`); solo se permite `INSERT`.
**Por qué**: la defendibilidad de la cadena de custodia (DD-07) no puede depender de la disciplina de la capa de aplicación; un insider o un bug la rompería. La garantía vive en la base.
**Alternativa considerada**: append-only por convención en el repositorio → un `UPDATE` directo a la DB lo viola; inaceptable para evidencia.

### D2 — Hash encadenado (hash_prev) por entrada del audit log
**Decisión**: cada fila del audit log incluye `hash_prev` = hash de la entrada anterior, formando una cadena ("blockchain rudimentaria", `04`) validable a diario.
**Por qué**: detecta inserción/borrado fuera de banda; un perito externo valida la cadena (DD-07). Junto con D1, hace el log inmutable y verificable.
**Alternativa considerada**: solo timestamps secuenciales → no detecta manipulación del contenido de una entrada.

### D3 — Estado de Sesión restringido al enum por constraint
**Decisión**: el `estado` de Sesión se restringe a `iniciada / activa / finalizada / flaggeada / cerrada` mediante enum/CHECK a nivel de base (`04` §Sesión).
**Por qué**: el ciclo de vida es central; un estado inválido corrompería el scoring y la cola de revisión. La invariante va en el motor.
**Alternativa considerada**: validar solo en Pydantic/aplicación → un `INSERT` directo lo viola.

### D4 — Evento como hypertable TimescaleDB con índices, compresión y agregados
**Decisión**: `evento` es una hypertable particionada por día, con índices `(session_id, timestamp)` y `(exam_id, timestamp)`, política de compresión (chunks <7d sin comprimir, >7d comprimidos ~10×) y continuous aggregates base (eventos/sesión/min, score/sesión, sesiones activas/examen, distribución por tipo).
**Por qué**: DD-05 + SU-06 — 4–5M filas/examen no las sostiene Postgres nativo; la compresión y los agregados (CQRS-lite, `08`) hacen viables la escala de escritura y la latencia de paneles.
**Alternativa considerada**: tabla Postgres nativa → se degrada, DELETE masivos costosos (DD-05).

### D5 — Embedding cifrado at-rest y eliminable; Consentimiento inmutable
**Decisión**: `embedding.vector` se almacena cifrado (KMS, `08`), con `versión` y fecha, y se elimina al egreso del estudiante; `consentimiento` es inmutable (acuse con `hash`).
**Por qué**: privacidad por diseño (DD-13), embedding sensible por defecto (SU-08, Ley 25.326), y el consentimiento debe ser un registro inalterable de la sesión.
**Alternativa considerada**: embedding en claro / consentimiento mutable → viola la clasificación sensible y la trazabilidad legal.

### D6 — Repositorios genéricos como puertos, dominio puro
**Decisión**: interfaces de repositorio por dominio en `domain`/`application`; adaptadores SQLAlchemy en `infrastructure/persistence`. El dominio no importa SQLAlchemy.
**Por qué**: Hexagonal (`08` §Patrones) — testabilidad y sustituibilidad de la persistencia.
**Alternativa considerada**: ORM activo en el dominio → acopla dominio a SQLAlchemy, rompe la pureza.

## Esquema de datos (resumen)

```
USUARIO(id, id_institucional, roles, email, attrs_federados)        [JIT desde IdP]
EXAMEN(id, nombre, parametros, detectores, umbral_score, ventana, retencion)
SESION(id, user_id→USUARIO, exam_id→EXAMEN, estado{enum}, score, clave_sesion, ts...)
ASIGNACION(proctor_id→USUARIO, exam_id→EXAMEN)                      [*—* proctor↔examen]
CONSENTIMIENTO(id, user_id, exam_id, version_texto, ts, hash)       [inmutable]
EMBEDDING(id, user_id, vector_cifrado, version, fecha)              [cifrado; borrar al egreso]
EVIDENCIA(id, session_id, uri_bucket, hash_cliente, firma_cliente,
          hash_backend, firma_maestra, output_reinferencia, meta)
CASO_DISC(id, session_id, estado, refs_evidencia, decisiones, vinculo_externo)  [hold]
AUDIT_LOG(id, actor, ts, ip, user_agent, accion, evidencia_id, proposito, hash_prev)
          ↑ trigger rechaza UPDATE/DELETE; hash_prev encadena

EVENTO  [HYPERTABLE TimescaleDB, particionada por día]
  (id, session_id, exam_id, tipo, severidad, ts_cliente, ts_backend,
   payload JSON, firma HMAC, schema_version)
  índices: (session_id, timestamp), (exam_id, timestamp)
  compresión: <7d sin comprimir; >7d comprimido (~10×)
  continuous aggregates: eventos/sesión/min · score/sesión · sesiones activas/examen · dist. por tipo
```

## Risks / Trade-offs

- **[El trigger append-only tiene un hueco / no rechaza alguna mutación]** → Mitigación: tests que **intentan** `UPDATE` y `DELETE` y verifican el `RAISE EXCEPTION` (D1); cobertura de los dos verbos.
- **[Encadenamiento de hash incorrecto / no validable]** → Mitigación: test que inserta N entradas y valida la cadena `hash_prev` extremo a extremo (D2).
- **[Estado de Sesión inválido por bypass de aplicación]** → Mitigación: constraint en el motor + test de `INSERT` con estado fuera del enum que debe fallar (D3).
- **[Hypertable mal creada / sin compresión / sin agregados]** → Mitigación: test que verifica la creación de la hypertable, sus índices y la política de compresión (D4).
- **[Embedding en claro o consentimiento mutable]** → Mitigación: D5 — campo cifrado y consentimiento sin path de update; revisión de privacidad (DPO).
- **Trade-off aceptado**: la compresión >7d encarece consultas históricas sobre datos comprimidos; aceptable porque los paneles leen de continuous aggregates, no del raw comprimido (`08` §CQRS-lite).

## Migration Plan

1. **Migración 002** (sobre la 001 de C-04 que ya habilitó la extensión): crea las tablas transaccionales, el enum de Sesión, el audit log + trigger + columna `hash_prev`, la hypertable de Evento con índices, las políticas de compresión y los continuous aggregates.
2. Implementar los repositorios genéricos (puertos + adaptadores SQLAlchemy).
3. Tests: enum de Sesión, trigger append-only rechaza UPDATE/DELETE, encadenamiento de hash, creación de hypertable e índices/compresión.
4. **Criterio de salida**: 002 aplica, las invariantes están en el motor y los tests pasan ⇒ desbloquea C-06.

**Rollback**: la 002 se revierte en dos pasos (convención de C-04) — primero quita agregados/trigger/políticas, luego las tablas; el esquema vuelve al estado post-001 (extensión presente, sin tablas).

## Open Questions

- Algoritmo exacto de cifrado del embedding y rotación de claves → lo opera infraestructura (`08` §Cifrado at-rest); aquí se modela el contrato del campo cifrado.
- Esquema de evento **versionado definitivo** y validación de firma HMAC de producción → C-10 (aquí se deja `schema_version` y `firma` como columnas, no la validación de producción).
- Política de retención por examen (valores concretos) → configurable por Examen; los valores los fija administración.
