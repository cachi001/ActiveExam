# Proposal — C-19 `retencion-holds`

> **Naturaleza del change**: backend **auxiliar** de cumplimiento legal. Governance **ALTO** (retención y supresión verificable, Ley 25.326). Implementa la aplicación automática de políticas de retención con holds (US-014, FR-14; RN-DSR-02). Depende de C-07 (modelo de datos / eventos / casos ya persistidos).

## Why

La normativa exige **retención y supresión verificable** sin acción manual (US-014, FR-14, RN-DSR-02). Un sistema de proctoring acumula datos personales de alto volumen (eventos en hypertable TimescaleDB, clips, embeddings, audit log, casos); conservarlos indefinidamente viola la minimización y la finalidad acotada del DPIA, y mantenerlos a mano "por las dudas" es exactamente lo que la ley prohíbe. El DPO (Ana) quiere que las políticas se apliquen **solas**, cumpliendo la normativa sin intervención.

Pero la retención no puede ser ciega: un **caso disciplinario abierto extiende automáticamente la retención** (hold) de la evidencia relacionada — borrar datos bajo investigación obstruiría un proceso legítimo (RN-DSR-02; Caso disciplinario "extiende la retención mientras esté abierto"). Y el embedding, dato biométrico sensible, debe **eliminarse al egreso del estudiante** (modelo de datos: "eliminado al egreso del estudiante"). Además, el volumen de eventos obliga a un ciclo de vida de datos: chunks recientes sin comprimir, comprimidos hasta un año, y **>1 año exportados a Parquet en object storage y eliminados de la base activa**.

## What Changes

Implementa la maquinaria de retención automática y holds del backend:

- **Aplicación automática de políticas de retención** configuradas por tipo de dato: clips, embeddings, eventos, audit log y casos. Un proceso periódico aplica cada política sin intervención manual (US-014 CA-1).
- **Ciclo de vida de eventos en TimescaleDB**: respeta la política de compresión (recientes sin comprimir, 7 días–1 año comprimidos) y **archiva los chunks > umbral a Parquet en object storage, eliminándolos de la base activa** (modelo de datos §Evento).
- **Holds por caso abierto**: un caso disciplinario abierto **extiende automáticamente la retención** de los datos relacionados; la retención normal no los elimina mientras el hold esté activo (US-014 CA-2; RN-DSR-02). Al cerrarse el caso, el hold se libera y los datos vuelven al régimen de retención normal.
- **Eliminación del embedding al egreso del estudiante**: cuando el estudiante egresa, su embedding biométrico cifrado se elimina (modelo de datos §Embedding).
- **Verificabilidad**: cada aplicación de política, archivado y eliminación deja rastro en el audit log append-only (retención y supresión verificable).

**BREAKING**: ninguno. Agrega procesos y políticas sobre el modelo existente; no cambia contratos de API de dominio.

## Capabilities

### New Capabilities

- `retention-policy-engine`: el motor que aplica automáticamente las políticas de retención configuradas por tipo de dato (clips, embeddings, eventos, audit log, casos), sin acción manual.
- `event-chunk-archival`: el ciclo de vida de los eventos en TimescaleDB — compresión por antigüedad y archivado de chunks > umbral a Parquet en object storage con eliminación de la base activa.
- `retention-holds`: los holds que extienden automáticamente la retención de los datos vinculados a un caso disciplinario abierto y los liberan al cerrarse.
- `embedding-egress-deletion`: la eliminación del embedding biométrico al egreso del estudiante.

### Modified Capabilities

(Ninguna — agrega capacidades nuevas sobre el modelo de datos de C-07; no modifica requisitos previos.)

## Impact

- **Dependencias entrantes**: C-07 (modelo de datos: Evento hypertable, Embedding, Caso disciplinario, Audit log, Configuración de retención). Sin esas entidades persistidas no hay sobre qué aplicar retención.
- **Decisiones que consume**: DD-13 + DPIA (minimización, retención configurable, derechos del titular), política de compresión/Parquet del modelo de eventos, Caso disciplinario como hold. Se coordina con **C-17** (DSR): una erasure diferida por hold en C-17 se reanuda cuando el hold se libera aquí.
- **Actores afectados**: DPO (configura y supervisa la retención), coordinador disciplinario (sus casos abiertos imponen holds), administrador del sistema (configura políticas), estudiante/titular (sus datos se eliminan al egreso o por política).
- **Riesgos mitigados**: incumplimiento de la Ley 25.326 (retención excesiva / supresión no verificable), retención biométrica más allá de lo necesario (mitigada por eliminación al egreso), borrado de evidencia bajo investigación (mitigado por holds). Coherente con L2.5: la retención no toma decisiones disciplinarias, solo gestiona el ciclo de vida del dato.
