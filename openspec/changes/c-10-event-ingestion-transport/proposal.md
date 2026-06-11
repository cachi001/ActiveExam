# Proposal — C-10 `event-ingestion-transport`

> ⚠️ **REALITY CHECK 2026-06-11 — implementación slim vs visión futura**
>
> - **Implementación ahora (rama "slim", prod Railway)**: persistencia en **tabla común `proctoring_event`** (Postgres puro, migración 0005). Screenshots adjuntos al evento (`screenshot_b64`, `screenshot_sha256`). Backplane Postgres `LISTEN/NOTIFY` estándar. **NO hay hypertable, NO hay TimescaleDB extension, NO hay clips de video** (la evidencia es screenshot por evento, no video continuo).
> - **Visión futura (rama "full", cuando c-03 valide volumen al pico)**: migrar a hypertable TimescaleDB con compresión nativa. El design body refleja esa visión — sigue siendo válido para Fase 2.
> - **Tasks afectadas**: persistencia (sección 4) opera contra tabla común, no hypertable. El resto (validación HMAC, fan-out, OTEL) aplica igual.

> **Naturaleza del change**: núcleo de monitoreo en tiempo real, governance **ALTO**. Es la **columna vertebral del pipeline de eventos**: el canal por el que el cliente (sensor no confiable) reporta lo que ocurre, el backend lo valida, lo firma server-side, lo persiste en TimescaleDB y lo propaga a los paneles. Todo lo de detección (C-11), evidencia (C-12), scoring (C-13), panel (C-15) y resiliencia (C-14) cuelga de este transporte.

## Why

El sistema de proctoring opera bajo un principio rector (RN-GLB-01): **el cliente es un sensor con sesgos conocidos, NO una fuente de verdad**. Cada evento que llega es entrada potencialmente hostil (zero trust). Sin un canal de ingesta que valide la firma de cada evento ANTES de persistir, re-infiera y firme server-side, la cadena probatoria se construye sobre un dato no validado y toda la evidencia downstream es indefendible.

Además, el NFR de capacidad endurecido (SU-06) exige sostener **1.000 concurrentes / ~2.100 pico / ~5.000 inserts/s** con un SLO de tiempo real estricto: propagación evento→panel **p99 < 500 ms** y **cero pérdida de eventos confirmados** (`14`, RN-CC-08). El transporte tiene que cumplir ese SLO sin acoplar el escalado de los canales.

El Flujo 3 describe la mecánica: el Web Worker produce eventos discretos, los manda por WebSocket, cada 5 s un heartbeat firmado; el backend valida cada firma, persiste en la hypertable y hace fan-out. Este change implementa **esa mecánica con calidad de producción**, sobre la infraestructura de transporte/backplane que **decide C-03** (no se asume aquí).

## What Changes

Construye el **canal de ingesta del estudiante y el fan-out a paneles**, con el esquema de evento versionado y firmado como contrato central.

- **Canal WebSocket del estudiante (bidireccional)**: transporta eventos, heartbeats y comandos backend→cliente. Handshake con `session_id` + JWT (validado contra JWKS de Keycloak) + `last_event_id` (gancho para que C-14 replantee la reconexión). Este canal es **separado** del panel del proctor y **no está bajo decisión de transporte** — el WebSocket bidireccional del estudiante es fijo (DD-16); lo que decide C-03 es el transporte del **panel** y el **backplane**.
- **Esquema de evento versionado y firmado**: `id`, `session_id`, `exam_id` (denormalizado), `tipo`, `severidad`, `ts_client`, `ts_backend` (completado al recibir), `payload` JSON, `firma` (HMAC-SHA256 con clave de sesión rotativa) y `schema_version`. Contrato versionado con **compatibilidad hacia atrás** (RN-EV-05).
- **Validación de firma server-side**: el backend valida la firma HMAC de **cada** evento contra la clave de sesión antes de persistir; un evento sin firma o con firma inválida se **rechaza** (no se persiste, se registra). Re-inferencia/firma server-side de lo que corresponda como versión confiable (zero trust, RN-GLB-01).
- **Heartbeat firmado cada 5 s**: prueba de vida de la sesión y del detector; firmado con HMAC y validado por el backend (RN-HB-01).
- **Persistencia en TimescaleDB hypertable**: inserción del evento en la hypertable de eventos (DD-05) con sus índices `(session_id, ts)` y `(exam_id, ts)`.
- **Fan-out a paneles vía backplane**: propagación del evento a los paneles suscriptos a través del **backplane ganador de C-03** (`LISTEN/NOTIFY` o Redis Pub/Sub), sin asumir cuál; el SLO de propagación es **p99 < 500 ms** y **cero pérdida de eventos confirmados**.
- **Tipos de evento del dominio**: rostro ausente, múltiples rostros, mirada desviada sostenida, postura, cambio de pestaña/pérdida de foco, monitor adicional, posible cambio de identidad, evidencia corrupta, heartbeat (RN-EV-04).

**El sistema NUNCA sanciona automáticamente (L2.5, RN-RV-07)**: este canal solo transporta y persiste señales; ninguna decisión disciplinaria se deriva de la ingesta.

## Capabilities

### New Capabilities

- `event-schema-contract`: el contrato del evento versionado y firmado — estructura, campos obligatorios, `schema_version` con compatibilidad hacia atrás, y la semántica de los tipos/severidades del dominio.
- `student-ws-channel`: el canal WebSocket bidireccional del estudiante — handshake autenticado (`session_id` + JWT + `last_event_id`), transporte de eventos/heartbeats/comandos, heartbeat firmado /5s.
- `event-signature-validation`: la validación server-side de la firma HMAC de cada evento y heartbeat antes de persistir, con rechazo del evento no firmado o con firma inválida (zero trust del cliente).
- `event-persistence-timescale`: la persistencia del evento validado en la hypertable de TimescaleDB con el timestamp de backend y los índices del modelo de datos.
- `event-fanout-backplane`: el fan-out del evento persistido a los paneles suscriptos vía el backplane ganador de C-03, bajo el SLO p99 < 500 ms y cero pérdida de eventos confirmados.

### Modified Capabilities

(Ninguna — no existen specs de dominio previas en `openspec/specs/` que este change modifique. Las capabilities de C-01/C-02 son de governance; C-03 no deja specs de dominio.)

## Impact

- **Dependencias entrantes**: `C-09` (prerrequisito directo, según CHANGES.md) y, transitivamente, el **veredicto de transporte/backplane de C-03** (qué backplane levantar para el fan-out). No se asume `LISTEN/NOTIFY` ni Redis: se consume el ganador.
- **Bloquea (downstream)**: C-11 (vision-engine — produce los eventos que este canal ingesta), C-12 (evidencia — el evento severo dispara la captura), C-13 (scoring — lee los eventos persistidos), C-14 (resiliencia — extiende el handshake con buffer/replay), C-15 (panel — consume el fan-out).
- **Contrato central**: el `event-schema-contract` es consumido por todos los downstream; su versionado con compatibilidad hacia atrás es lo que permite que el cliente y los detectores evolucionen sin romper la ingesta.
- **Actores/sistemas afectados**: estudiante (origen de los eventos vía Web Worker), backend FastAPI (validador/persistidor/fan-out), TimescaleDB (hypertable), paneles de proctor (receptores del fan-out).
- **Riesgo principal**: que el fan-out no sostenga p99 < 500 ms al pico — mitigado porque la infraestructura de backplane ya viene **medida y decidida por C-03**, no apostada.
