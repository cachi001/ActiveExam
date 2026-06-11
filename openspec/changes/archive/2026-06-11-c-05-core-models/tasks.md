# Tasks — C-05 `core-models`

> **Naturaleza**: estas tareas materializan el **modelo de datos del dominio** y sus invariantes en el motor (migración 002), más los repositorios como puertos. El Done de cada tarea de invariante es **un test que verifica la garantía en la base** (el trigger rechaza, el enum restringe, el hash encadena, la hypertable existe), no solo el código de aplicación. El change desbloquea C-06 cuando 002 aplica y los tests de invariantes pasan.
> Dependencia: requiere C-04 (repo por capas, Alembic, extensión TimescaleDB habilitada por la migración 001).

## 1. Entidades transaccionales (capability `domain-entities`)

- [x] 1.1 Modelar Usuario (JIT desde IdP), Examen, Asignación (proctor↔examen *—*); Done: tablas y relaciones de identidad/examen presentes
- [x] 1.2 Modelar Evidencia (hashes/firmas de cadena de custodia, `uri_bucket`) y Caso disciplinario (estado, refs, hold); Done: entidades de evidencia/custodia presentes
- [x] 1.3 Modelar Embedding **cifrado at-rest** (versión, fecha, eliminable al egreso) y Consentimiento **inmutable** (versión_texto, ts, hash); Done: campos sensibles modelados (DD-13, SU-08, Ley 25.326)
- [x] 1.4 Verificar las cardinalidades de `04` (FKs y tabla de unión Asignación); Done: relaciones coherentes con el ERD

## 2. Ciclo de vida de la Sesión (capability `session-lifecycle-enum`)

- [x] 2.1 Modelar Sesión (entidad central: user_id, exam_id, estado, score, clave_sesion, timestamps); Done: entidad central presente
- [x] 2.2 Restringir `estado` al enum `iniciada/activa/finalizada/flaggeada/cerrada` por constraint de base; Done: constraint en el motor
- [x] 2.3 Test: estado válido aceptado; estado fuera del enum **rechazado por la base** aun por fuera de la aplicación; Done: constraint de enum verificada

## 3. Audit log append-only (capability `append-only-audit-log`)

- [x] 3.1 Crear la tabla audit_log con sus columnas (`04` §Audit log) y la columna `hash_prev`; Done: tabla presente
- [x] 3.2 Crear el **trigger** que rechaza `UPDATE`/`DELETE` (RAISE EXCEPTION), permitiendo solo `INSERT`; Done: inmutabilidad en el motor (DD-07)
- [x] 3.3 Implementar el encadenamiento de hash (`hash_prev` = hash de la entrada anterior); Done: cadena construida al insertar
- [x] 3.4 Test: INSERT permitido; **UPDATE y DELETE rechazados** por el trigger; Done: rechazo de mutaciones verificado para ambos verbos
- [x] 3.5 Test: cadena de hash consistente extremo a extremo y ruptura detectable; Done: encadenamiento de hash verificado

## 4. Evento hypertable TimescaleDB (capability `event-hypertable`)

- [x] 4.1 Crear el Evento como **hypertable** particionada por día con el esquema de `04` §Evento; Done: hypertable creada sobre la extensión de C-04
- [x] 4.2 Crear los índices `(session_id, timestamp)` y `(exam_id, timestamp)`; Done: ambos índices presentes
- [x] 4.3 Configurar la política de **compresión** (chunks <7d sin comprimir, >7d comprimidos); Done: política activa
- [x] 4.4 Crear los **continuous aggregates base** (eventos/sesión/min, score/sesión, sesiones activas/examen, distribución por tipo); Done: agregados materializados
- [x] 4.5 Test: la hypertable se crea con sus índices y la política de compresión; Done: creación de hypertable verificada

## 5. Migración 002 y repositorios (capabilities `domain-entities`, `domain-repositories`)

- [x] 5.1 Consolidar la **migración 002** (tablas + enum + trigger + hash_prev + hypertable + índices + compresión + agregados) sobre la 001 de C-04, en la convención destructiva-en-dos-pasos; Done: 002 aplica y revierte en dos pasos
- [x] 5.2 Implementar los **repositorios genéricos (puertos)** por dominio con adaptadores SQLAlchemy en `infrastructure/persistence`, manteniendo el dominio puro; Done: puerto + adaptador por dominio
- [x] 5.3 Garantizar que el repositorio del audit log es solo-append y el del Consentimiento no expone update; Done: repositorios coherentes con las invariantes de motor
- [x] 5.4 Declarar el criterio de salida: 002 aplicada + invariantes en el motor + tests verdes ⇒ desbloquea C-06; Done: modelo de datos listo y documentado
