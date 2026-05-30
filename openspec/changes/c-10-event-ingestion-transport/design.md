# Design — C-10 `event-ingestion-transport`

> Diseño técnico del **canal de ingesta de eventos y el fan-out a paneles**, con calidad de producción. Implementa la mecánica del Flujo 3 sobre la infraestructura de transporte/backplane que decide C-03 (no se asume). El cliente es sensor no confiable: el backend valida la firma de cada evento, re-infiere/re-firma server-side y persiste.

## Context

El stack es React + FastAPI (mono-hilo escalado horizontal tras Nginx, DD-10) + PostgreSQL/TimescaleDB + Keycloak + backplane (ganador de C-03). El backend sigue Clean/Hexagonal pragmática: dominio puro (contrato de evento, reglas de severidad), aplicación (caso de uso de ingesta), infraestructura (adaptadores de WS, persistencia Timescale, backplane, validación de firma, JWKS) y presentación delgada (handler WebSocket).

**NFR (SU-06, `14`)**: 1.000 concurrentes sostenido / ~2.100 pico / ~5.000 inserts/s. **SLO tiempo real**: propagación evento→panel p99 < 500 ms; cero pérdida de eventos confirmados (RN-CC-08).

**Constraints duras del dominio**:
- El cliente es **sensor no confiable** (RN-GLB-01): toda firma se valida server-side; la fuente de verdad es el servidor.
- El sistema **NUNCA sanciona automáticamente** (L2.5, RN-RV-07): la ingesta solo transporta y persiste.
- La **arquitectura de transporte/backplane la decide C-03**: el fan-out se programa contra un puerto sustituible, no contra `LISTEN/NOTIFY` ni Redis directamente.
- El **WebSocket bidireccional del estudiante es fijo** (DD-16) y separado del panel; no está en disputa.

**Stakeholders**: estudiante (origen), backend (validador/persistidor/fan-out), TimescaleDB, paneles de proctor (receptores), y los downstream C-11/C-12/C-13/C-14/C-15 que consumen el contrato y el canal.

## Goals / Non-Goals

**Goals:**
- Definir el **contrato de evento versionado y firmado** con compatibilidad hacia atrás.
- Implementar el **canal WS bidireccional del estudiante** con handshake autenticado (`session_id` + JWT + `last_event_id`) y heartbeat firmado /5s.
- **Validar la firma HMAC de cada evento/heartbeat server-side** antes de persistir; rechazar el no firmado o inválido.
- **Persistir** en la hypertable de TimescaleDB con `ts_backend` y los índices del modelo de datos.
- **Fan-out** a paneles vía el backplane **ganador de C-03** (puerto sustituible), bajo p99 < 500 ms y cero pérdida.

**Non-Goals:**
- NO decidir el transporte del panel ni el backplane (lo decide C-03; aquí se consume el ganador).
- NO implementar el buffer IndexedDB / replay de reconexión (C-14 lo construye sobre el `last_event_id` que este change expone).
- NO implementar los detectores de visión que producen los eventos (C-11).
- NO implementar la captura/cadena de custodia de evidencia (C-12), el scoring (C-13) ni el panel (C-15).
- NO aplicar ninguna sanción ni lógica disciplinaria (L2.5).

## Decisions

### D1 — Contrato de evento versionado en el dominio, no en la presentación
**Decisión**: el contrato (`id`, `session_id`, `exam_id`, `tipo`, `severidad`, `ts_client`, `ts_backend`, `payload`, `firma`, `schema_version`) vive en el dominio puro, con `schema_version` y compatibilidad hacia atrás como invariante.
**Por qué**: es el contrato que C-11…C-15 consumen; debe ser estable y testeable sin acoplarse al transporte. El versionado permite evolucionar el cliente sin romper la ingesta (RN-EV-05).
**Alternativa considerada**: validar el esquema en el handler WS → acopla el contrato al transporte y dificulta el versionado.

### D2 — Validación de firma como puerto, antes de cualquier persistencia
**Decisión**: la validación HMAC contra la clave de sesión rotativa es un puerto de infraestructura invocado por el caso de uso de ingesta **antes** de persistir; el evento no firmado o inválido se rechaza y se registra, nunca se persiste ni propaga.
**Por qué**: zero trust del cliente (RN-GLB-01); persistir antes de validar contaminaría la cadena probatoria con dato hostil.
**Alternativa considerada**: persistir y validar en background → ventana en la que dato no validado es visible al panel/scoring.

### D3 — Fan-out contra un puerto de backplane sustituible (ganador de C-03)
**Decisión**: el fan-out publica en un puerto `EventBackplane` con dos adaptadores intercambiables: `LISTEN/NOTIFY` y Redis Pub/Sub. El ganador de C-03 selecciona el adaptador por configuración, sin tocar la lógica de ingesta.
**Por qué**: C-03 decide el backplane por métrica; este change no debe asumir el resultado. El puerto aísla la decisión y permite que C-03 cambie el veredicto sin reescribir C-10.
**Alternativa considerada**: programar directo contra `LISTEN/NOTIFY` (la hipótesis A4) → si C-03 promueve Redis, habría retrabajo.

### D4 — `last_event_id` en el handshake como gancho para C-14, sin implementar el replay
**Decisión**: el handshake acepta y registra `last_event_id`; este change expone la capacidad de consultar eventos posteriores (índice `(session_id, ts)`), pero el buffer IndexedDB, el backoff y el drenaje deduplicado los implementa C-14.
**Por qué**: separa el contrato del transporte (C-10) de la política de resiliencia (C-14), manteniendo cada change cohesivo.
**Alternativa considerada**: meter el replay completo en C-10 → infla el change y mezcla responsabilidades.

### D5 — La ingesta no deriva ninguna sanción (L2.5)
**Decisión**: el caso de uso de ingesta termina en persistir + fan-out; ninguna severidad (ni crítica) dispara acción punitiva automática.
**Por qué**: L2.5 y RN-RV-07 — ninguna sanción es automática; la decisión es siempre humana.
**Alternativa considerada**: ninguna (es una regla dura del dominio).

## Arquitectura del flujo de ingesta

```
[Web Worker]                [FastAPI instancia]                 [TimescaleDB]   [Backplane C-03]   [Paneles]
   evento firmado ──WS──►  handshake(session_id,JWT,last_event_id)
   heartbeat /5s    ──WS──►  ├─ valida JWT (JWKS Keycloak)
                             ├─ valida firma HMAC (clave sesión) ──┐
                             │     inválida/ausente → RECHAZA ─────┘ (log, no persiste, no fan-out)
                             ├─ re-firma/re-infiere server-side (versión confiable)
                             ├─ completa ts_backend ──persiste──►  hypertable (idx session/exam)
                             └─ publica ───────────────────────────────────────► backplane ──► paneles
                                                                                  (p99 < 500 ms, cero pérdida)
```

| Concern | Puerto / Adaptador | Notas |
|---------|--------------------|-------|
| Autenticación del canal | JWKS de Keycloak | validar firma/exp/aud/iss en handshake y periódico (RN-AU-03) |
| Validación de firma | `EventSignatureVerifier` (HMAC clave sesión) | antes de persistir; rechazo del no firmado (D2) |
| Persistencia | `EventRepository` (TimescaleDB hypertable) | `ts_backend`, índices `(session_id,ts)` / `(exam_id,ts)` |
| Fan-out | `EventBackplane` (LISTEN/NOTIFY \| Redis Pub/Sub) | adaptador = ganador de C-03 (D3) |

## Risks / Trade-offs

- **[Asumir el backplane equivocado]** → Mitigación: D3 — puerto sustituible; el ganador de C-03 entra por configuración.
- **[Persistir dato no validado]** → Mitigación: D2 — validación de firma antes de cualquier persistencia o fan-out.
- **[Fan-out no sostiene p99 < 500 ms al pico]** → Mitigación: la infraestructura de backplane ya viene medida por C-03; aquí se respeta el SLO como requisito de aceptación.
- **[Romper downstream al evolucionar el esquema]** → Mitigación: D1 — `schema_version` con compatibilidad hacia atrás; versión no soportada se rechaza explícitamente.
- **Trade-off aceptado**: exponer solo el gancho `last_event_id` (no el replay) deja la resiliencia para C-14; mantiene C-10 cohesivo a costa de una dependencia explícita.

## Migration Plan

No hay sistema previo en producción. La puesta en marcha:
1. Definir el contrato de evento versionado en el dominio (migración Alembic de la hypertable si no existe aún de C-09).
2. Implementar el handler WS con handshake autenticado y heartbeat /5s.
3. Implementar el verificador de firma y conectarlo antes de la persistencia.
4. Implementar el repositorio de persistencia en la hypertable con índices.
5. Implementar el puerto de backplane con ambos adaptadores; seleccionar el ganador de C-03 por configuración.
6. Verificar SLO (p99 < 500 ms) y cero pérdida bajo carga.

**Rollback**: al ser el primer canal de ingesta, no hay rollback de datos; un fallo se resuelve corrigiendo el adaptador correspondiente sin afectar el contrato.

## Open Questions

Las que este change **cierra**:
- ¿Cuál es el contrato de evento versionado definitivo y su política de compatibilidad? → `event-schema-contract`.
- ¿Cómo se valida la firma server-side y se rechaza el evento hostil? → `event-signature-validation`.

Las que **quedan fuera** (otros changes):
- Qué backplane concreto se usa en producción → veredicto de C-03 (este change lo consume por puerto).
- Buffer IndexedDB, backoff y replay deduplicado → C-14.
- Detectores que producen los eventos → C-11.
