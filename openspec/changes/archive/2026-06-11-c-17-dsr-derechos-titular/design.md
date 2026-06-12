# Design — C-17 `dsr-derechos-titular`

## Context

El proyecto Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3 WORM, backend Clean/Hexagonal, NFR de 1.000 concurrentes sostenido / ~2.100 pico) debe ofrecer al titular una vía operativa para ejercer sus derechos bajo la Ley 25.326 (US-013, FR-13, UC-05; Flujo 9). El DPIA aprobado en C-01 declara estos derechos como nativos; este change los implementa en el recurso `POST /api/v1/dsr/{type}`.

**Constraints:**
- La eliminación física del binario en el bucket está **subordinada al Object Lock (modo Compliance, WORM)**: durante la retención el clip no se puede borrar ni siquiera por el propietario (RN-CC-06). El derecho al olvido sobre el binario se materializa cuando expira la retención; mientras tanto se elimina la referencia/acceso y se anonimiza el resto.
- El embedding **sí** es cifrado at-rest en tabla transaccional y se puede eliminar inmediatamente.
- El audit log es **append-only** (trigger rechaza UPDATE/DELETE; hashes encadenados): la trazabilidad de la operación DSR se agrega como entradas nuevas, nunca borrando ni mutando.
- Ninguna sanción es automática (L2.5): la oposición a decisiones automatizadas (RN-DSR-04) está cubierta por arquitectura, no por un flujo nuevo.

**Stakeholders:** estudiante/titular, DPO, coordinador disciplinario (holds).

## Goals / Non-Goals

**Goals:**
- Exponer `POST /api/v1/dsr/{type}` para `access`, `rectification`, `erasure`, `portability`, autenticado contra el titular.
- Implementar el derecho al olvido con verificación de holds, eliminación de binarios + embeddings, anonimización con residual y diferimiento ante casos abiertos.
- Garantizar la trazabilidad de toda operación DSR en el audit log y la respuesta en plazo legal.

**Non-Goals:**
- NO construir la UI del estudiante para ejercer derechos (frontend va aparte).
- NO definir las políticas de retención automáticas ni el archivado de chunks — eso es C-19.
- NO implementar la cadena de custodia ni el bucket WORM (C-12); aquí solo se consume.
- NO mover el plazo legal a un valor mágico: se modela como configuración, el valor lo fija legal.

## Decisions

### D1 — Un solo endpoint parametrizado por `{type}`, lógica por tipo en el dominio
**Decisión**: `POST /api/v1/dsr/{type}` enruta a un caso de uso por derecho (access / rectification / erasure / portability) en la capa de aplicación (hexagonal). El adaptador HTTP valida `{type}` contra un enum; el dominio no conoce HTTP.
**Por qué**: respeta Clean/Hexagonal; un endpoint coherente con el contrato de KB (`02_descripcion_general` y `07_flujos`); facilita testear cada derecho de forma aislada.

### D2 — Verificación de holds como precondición de toda eliminación/anonimización
**Decisión**: un servicio de dominio `HoldVerifier` consulta casos disciplinarios abiertos vinculados al titular (vía sesiones → evidencia → caso). Si hay al menos uno abierto, la eliminación se **difiere**: se registra la solicitud como pendiente con causa, no se borra nada, y se notifica al titular el motivo legal.
**Por qué**: borrar evidencia bajo investigación rompería la cadena de custodia y obstruiría un proceso legítimo (Flujo 9 caso de error; RN-DSR-02 hold).

### D3 — Eliminación = borrado de embeddings + revocación de acceso al binario + anonimización con residual
**Decisión**: ante erasure sin holds: (a) eliminar embeddings cifrados del titular; (b) para clips, eliminar la referencia y revocar acceso; el binario físico se purga cuando expira el Object Lock (purga diferida registrada); (c) anonimizar los registros de dominio (sesiones, eventos, consentimientos) sustituyendo identificadores personales por un seudónimo irreversible, conservando un **residual sin datos personales** que prueba que la sesión existió y que la eliminación se ejecutó.
**Por qué**: cumple RN-DSR-03 (residual sin datos personales) respetando el WORM (RN-CC-06).

### D4 — Trazabilidad por audit log append-only, sin reexponer lo eliminado
**Decisión**: cada operación DSR (incluida la diferida) escribe entradas en el audit log con `actor`=titular, `acción`=dsr.{type}, `propósito`, `timestamp`, encadenadas por hash. El audit log registra **que** la operación ocurrió y su resultado, no los datos personales eliminados.
**Por qué**: hace la operación verificable en auditoría (CA-2) sin violar la minimización ni resucitar datos borrados.

### D5 — Plazo legal configurable; operaciones diferidas marcadas como pendientes
**Decisión**: el plazo legal de respuesta es configuración del sistema; las erasures diferidas por hold quedan en estado pendiente con su causa y se reevalúan al cerrar el caso (gancho con C-19, que aplica retención/holds).
**Por qué**: la normativa puede cambiar el plazo; el diferimiento debe ser auditable y reanudable.

## Risks / Trade-offs

- **Riesgo**: el WORM impide borrar el binario "ya"; un titular podría interpretar incumplimiento. **Mitigación**: documentar la purga diferida por expiración de Object Lock como parte de la respuesta legal y registrarla.
- **Riesgo**: anonimización incompleta deja datos personales reidentificables. **Mitigación**: tests específicos de anonimización que verifican ausencia de PII en el residual.
- **Trade-off**: un solo endpoint parametrizado vs. cuatro endpoints. Se elige el parametrizado por coherencia con el contrato de KB.

## Migration Plan

Recurso nuevo; sin migración de datos. Requiere: enum de `dsr_type`, estado de solicitud DSR (incl. `diferida`), y los servicios `HoldVerifier` / `Anonymizer`. No rompe contratos existentes.

## Open Questions

- Valor exacto del plazo legal de respuesta (lo fija legal; aquí es configuración).
- Alcance preciso del "residual" mínimo que se conserva tras anonimizar (a validar con DPO).
