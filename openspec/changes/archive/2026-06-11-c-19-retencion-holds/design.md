# Design — C-19 `retencion-holds`

## Context

El proyecto Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3 WORM, backend Clean/Hexagonal, NFR 1.000 sostenido / ~2.100 pico) debe aplicar políticas de retención automáticas con holds (US-014, FR-14, RN-DSR-02) sobre el modelo de datos de C-07. El DPO quiere cumplimiento sin acción manual.

**Constraints:**
- Los eventos viven en una **hypertable TimescaleDB** particionada por chunks diarios. La política de ciclo de vida: chunks recientes (7 días) sin comprimir; 7 días–1 año comprimidos (~10×); **>1 año exportados a Parquet en object storage y eliminados de la base activa** (modelo de datos §Evento).
- El **embedding** es dato biométrico sensible, cifrado at-rest, **eliminado al egreso del estudiante** (modelo de datos §Embedding).
- Un **caso disciplinario abierto extiende la retención** (hold) de los datos relacionados; al cerrarse, libera el hold (§Caso disciplinario).
- El **audit log es WORM/append-only**: su "retención" significa archivado, nunca borrado dentro de la ventana de retención legal; las operaciones de retención se registran en él.
- Los binarios en bucket están bajo **Object Lock Compliance**: no se borran antes de expirar la retención.

**Stakeholders:** DPO, coordinador disciplinario, administrador del sistema, estudiante/titular.

## Goals / Non-Goals

**Goals:**
- Aplicar automáticamente políticas de retención por tipo de dato, sin intervención manual.
- Archivar chunks de eventos > umbral a Parquet y eliminarlos de la base activa.
- Implementar holds: un caso abierto extiende la retención; cerrarlo la libera.
- Eliminar el embedding al egreso del estudiante.
- Dejar toda operación de retención verificable en el audit log.

**Non-Goals:**
- NO implementar el endpoint DSR ni el derecho al olvido a demanda (eso es C-17).
- NO construir el modelo de datos ni la hypertable (eso es C-07).
- NO definir los valores numéricos de los plazos legales: son configuración (los fija legal/DPO).
- NO gestionar el ciclo de vida disciplinario del caso (solo lee su estado abierto/cerrado).

## Decisions

### D1 — Motor de retención dirigido por configuración, ejecutado periódicamente
**Decisión**: un job periódico recorre las políticas de retención configuradas por tipo de dato (clips, embeddings, eventos, audit log, casos) y aplica cada una respetando holds y Object Lock. Los plazos son configuración, no constantes.
**Por qué**: US-014 CA-1 exige aplicación automática sin acción manual; la configuración permite ajustar plazos sin desplegar código (RN-GLB-04: despliegues fuera de ventana de examen).

### D2 — Verificación de holds antes de cualquier eliminación
**Decisión**: antes de eliminar o archivar datos sujetos a hold, el motor verifica si existe un caso disciplinario abierto vinculado. Si lo hay, **extiende la retención** y omite la eliminación; al cerrarse el caso, el siguiente ciclo libera el hold y aplica la retención normal.
**Por qué**: RN-DSR-02 y §Caso disciplinario; borrar evidencia bajo investigación es inaceptable. Esto se coordina con C-17: una erasure diferida por hold se reanuda cuando el hold se libera aquí.

### D3 — Archivado de eventos a Parquet con eliminación de la base activa
**Decisión**: para la hypertable de eventos, el motor respeta la compresión nativa de TimescaleDB y, para chunks > umbral (p. ej. 1 año), exporta a Parquet en object storage y los elimina (drop chunk) de la base activa. El dato queda accesible vía object storage, no en la base caliente.
**Por qué**: modelo de datos §Evento lo especifica; mantiene la base activa acotada para sostener el NFR de carga sin perder los datos históricos.

### D4 — Eliminación del embedding al egreso
**Decisión**: ante el egreso del estudiante, el motor (o un disparador del ciclo de vida del usuario) elimina el embedding cifrado del titular. La eliminación se registra en el audit log.
**Por qué**: minimización del dato biométrico sensible; el embedding no debe sobrevivir a la relación que lo justifica (§Embedding).

### D5 — Toda operación de retención es verificable
**Decisión**: cada aplicación de política, archivado de chunk y eliminación deja una entrada en el audit log append-only (qué política, qué dato, cuándo, resultado), sin reexponer PII eliminada.
**Por qué**: "retención y supresión verificable" es un requisito de cumplimiento (checklist legal); sin trazabilidad no hay prueba de cumplimiento.

## Risks / Trade-offs

- **Riesgo**: un hold no detectado borra evidencia bajo investigación. **Mitigación**: la verificación de hold es precondición dura, con test específico de hold por caso abierto.
- **Riesgo**: el archivado a Parquet falla a medias y deja datos inconsistentes (en activa y en object storage). **Mitigación**: archivar primero, verificar la exportación, y solo entonces hacer drop del chunk.
- **Trade-off**: drop de chunk de la base activa vs consultabilidad inmediata del histórico. Se prioriza la base caliente acotada (NFR de carga); el histórico queda en object storage.

## Migration Plan

Agrega un motor de retención, definiciones de política por tipo de dato y un mecanismo de hold sobre el modelo de C-07. Requiere la configuración de retención por defecto (seed) y acceso de solo metadatos a los casos para evaluar holds. No migra datos existentes; comienza a aplicar políticas desde su despliegue.

## Open Questions

- Valores de los umbrales/plazos por tipo de dato (los fija el DPO/legal; aquí son configuración).
- Señal exacta de "egreso del estudiante" (evento del directorio institucional vs proceso administrativo) — a alinear con C-07/C-06.
