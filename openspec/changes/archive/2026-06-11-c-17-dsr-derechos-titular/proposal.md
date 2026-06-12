# Proposal — C-17 `dsr-derechos-titular`

> ⚠️ **REALITY CHECK 2026-06-11 — corrección de vocabulario "clips" → "screenshots"**
>
> - **Implementación ahora (rama "slim")**: la evidencia binaria que el DSR tiene que borrar/anonimizar son **screenshots por evento** (`proctoring_event.screenshot_b64`), no video clips. El concepto de erasure es el mismo, solo cambia el tipo de binario.
> - **MinIO/S3 WORM con Object Lock**: aplica igual — los screenshots subidos al bucket de evidencia tienen Object Lock; la erasure física se difiere hasta que expire el lock (eso no cambia con slim).
> - **Autenticación del titular**: hoy usa **JWT propio (c-55 archivado)** no Keycloak (c-52 archivado pero diferido). El design dice "Keycloak" — al implementar, usar el provider JWT activo.
> - **Visión futura**: cuando se active Keycloak (con integración LMS/LTI), reemplazar el auth provider. La lógica de DSR (`HoldVerifier`, `Anonymizer`, erasure de embeddings cifrados) no cambia.

> **Naturaleza del change**: backend **auxiliar** de cumplimiento legal. Governance **CRÍTICO** (Ley 25.326, derechos del titular). Implementa el endpoint `POST /api/v1/dsr/{type}` y la maquinaria de acceso / rectificación / eliminación / portabilidad, con verificación de holds y trazabilidad en audit log. Depende de C-06 (autenticación / Keycloak para identificar al titular).

## Why

La Ley 25.326 (y la reforma que anticipa portabilidad y oposición a decisiones automatizadas) obliga a que el titular pueda ejercer **acceso, rectificación, eliminación y portabilidad** sobre sus datos personales (US-013, FR-13, UC-05; RN-DSR-01/03/04). El DPIA aprobado en C-01 declara estos derechos como **nativos por diseño**, no como un anexo. Un sistema de proctoring que trata biometría (embeddings, clips) sin una vía operativa y **verificable en auditoría** para ejercer estos derechos es legalmente indefendible.

El requisito no es solo "borrar": el derecho al olvido (Flujo 9) debe **respetar los holds** — un caso disciplinario abierto extiende la retención y **difiere** la eliminación hasta cerrarlo (RN-DSR-02 / Caso disciplinario como hold). Eliminar evidencia bajo investigación rompería la cadena de custodia y obstruiría un proceso legítimo. La eliminación, además, debe ser **completa pero no destructiva de la trazabilidad**: borra binarios y embeddings, anonimiza registros y conserva un **residual sin datos personales** que prueba que la operación ocurrió, en plazo legal y verificable.

## What Changes

Implementa el recurso DSR del backend (`/api/v1/dsr`) con los cuatro derechos del titular:

- **`POST /api/v1/dsr/access`** (acceso): devuelve al titular el conjunto de sus datos personales tratados por el sistema (sesiones, eventos, evidencia asociada, embeddings — metadatos, consentimientos), en formato legible.
- **`POST /api/v1/dsr/rectification`** (rectificación): permite corregir datos personales rectificables del titular; cada rectificación queda registrada en el audit log.
- **`POST /api/v1/dsr/erasure`** (eliminación / derecho al olvido, Flujo 9): **verifica primero la ausencia de holds** (casos disciplinarios abiertos). Sin holds → elimina binarios (clips en bucket — sujeto a expiración de Object Lock) y embeddings, anonimiza los registros de dominio dejando un **residual sin datos personales**, y responde en plazo legal. Con holds → **difiere** la eliminación, informa el motivo y la deja pendiente hasta el cierre del caso.
- **`POST /api/v1/dsr/portability`** (portabilidad): exporta los datos personales del titular en un formato estructurado, común y de lectura mecánica (p. ej. JSON), para que el titular los porte.

Transversal a los cuatro:

- **Verificación de holds** centralizada: consulta de casos disciplinarios abiertos vinculados al titular antes de cualquier eliminación o anonimización.
- **Trazabilidad obligatoria**: toda operación DSR genera entradas en el **audit log append-only** (actor=titular, acción, propósito, timestamp), de modo que la operación sea verificable en auditoría sin exponer los datos eliminados.
- **Respuesta en plazo legal**: la operación se confirma dentro del plazo que exige la normativa; las operaciones diferidas (por hold) quedan registradas como pendientes con su causa.
- **Oposición a decisiones automatizadas (RN-DSR-04)**: se cumple **por arquitectura** — ninguna sanción es automática (L2.5); el endpoint documenta y referencia esta garantía, no la implementa como acción separada.

**BREAKING**: ninguno. Es un recurso nuevo del backend; no modifica contratos existentes.

## Capabilities

### New Capabilities

- `dsr-rights-endpoint`: el recurso `POST /api/v1/dsr/{type}` que expone acceso, rectificación, eliminación y portabilidad al titular autenticado, con respuesta en plazo legal.
- `dsr-erasure-with-holds`: la lógica del derecho al olvido que verifica holds, elimina binarios + embeddings, anonimiza dejando residual sin datos personales, y difiere ante casos abiertos (Flujo 9, RN-DSR-02/03).
- `dsr-auditability`: la trazabilidad de toda operación DSR en el audit log append-only, verificable en auditoría sin reexponer datos eliminados.

### Modified Capabilities

(Ninguna — introduce un recurso nuevo; no modifica capacidades previas.)

## Impact

- **Dependencias entrantes**: C-06 (autenticación / Keycloak) para identificar al titular que ejerce el derecho. Consume el modelo de Caso disciplinario (hold), Embedding, Evidencia y Audit log definidos en el modelo de datos.
- **Decisiones que consume**: DD-13 + DPIA (privacidad por diseño, derechos del titular nativos), clasificación del embedding como dato sensible (C-01), cadena de custodia WORM (la expiración de Object Lock condiciona cuándo el binario puede borrarse físicamente).
- **Actores afectados**: estudiante/titular (ejerce los derechos), DPO (supervisa, recibe la trazabilidad), coordinador disciplinario (sus casos abiertos imponen holds).
- **Riesgos mitigados**: incumplimiento de la Ley 25.326 (derechos del titular), eliminación de evidencia bajo investigación (mitigado por verificación de holds), pérdida de trazabilidad de la propia eliminación (mitigado por residual + audit log).
