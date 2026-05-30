# Design — C-14 `resiliencia-reconexion`

> Diseño técnico de la **resiliencia de red sin pérdida** (frontend / transport) sobre el canal WS del estudiante de C-10. Buffer IndexedDB, reconexión con backoff+jitter, replay ordenado y deduplicación por `event_id` (exactly-once lógico). Cero pérdida de eventos confirmados; no penalizar al estudiante por su red.

## Context

El canal WS del estudiante (C-10) es el transporte; este change añade la **capa de resiliencia** en `frontend/src/transport/` (buffer IndexedDB, reconexión, replay). El backend ya expone el gancho `last_event_id` en el handshake y la consulta de eventos posteriores (índice `(session_id, ts)` de C-10), y deduplica por `event_id` contra la hypertable.

**Constraints duras del dominio**:
- **Cero pérdida de eventos confirmados** (RN-CC-08): un corte de red no puede perder evidencia.
- **No penalizar injustamente** al estudiante por mala red: la resiliencia existe para que un corte no parezca anomalía.
- **Exactly-once lógico** (RN-HB-03): ni pérdida ni duplicados en el replay.
- **El sistema NUNCA sanciona automáticamente** (L2.5, RN-RV-07): el evento crítico por corte > 5 min es señal para el panel, no sanción.
- Se apoya en el **canal y los ganchos de C-10**; no redefine el transporte ni el contrato de evento.

**NFR de escala (SU-06)**: hasta ~2.100 clientes concurrentes; un corte masivo implica miles de reconexiones casi simultáneas — el thundering herd es un riesgo real que el jitter mitiga (RN-HB-05).

**Stakeholders**: estudiante con conexión inestable (beneficiario), backend (reenvía faltantes y deduplica), panel (recibe la señal de corte prolongado), y C-11/C-12 que dependen de que no se pierdan los eventos que producen/protegen.

## Goals / Non-Goals

**Goals:**
- Persistir eventos en un **buffer circular IndexedDB** resistente a cortes.
- Reconectar con **backoff exponencial + jitter 20%** y handshake con `last_event_id`.
- **Drenar el buffer en orden** y **deduplicar por `event_id`** (exactly-once lógico).
- Aplicar la **política por duración**: < 5 min sin pérdida, > 5 min evento crítico al reconectar.

**Non-Goals:**
- NO implementar el canal WS, el contrato de evento, la validación de firma ni la persistencia (es de C-10; este change los consume).
- NO implementar el backplane ni el fan-out a paneles (C-10).
- NO producir los eventos de visión (C-11) — este buffer los protege, no los genera.
- NO aplicar ninguna sanción por corte prolongado (L2.5): solo emite la señal.

## Decisions

### D1 — Buffer circular en IndexedDB, no en memoria
**Decisión**: persistir los eventos en un buffer circular en IndexedDB, no solo en memoria.
**Por qué**: un corte de red puede coincidir con un refresh o un cierre de pestaña; IndexedDB sobrevive a eso y garantiza cero pérdida (RN-HB-02). Circular para acotar el uso de almacenamiento local en cortes largos.
**Alternativa considerada**: buffer en memoria → se pierde ante refresh/cierre; viola RN-CC-08.

### D2 — Reconexión con backoff exponencial + jitter 20% (no fijo)
**Decisión**: backoff exponencial con jitter del 20% en cada reintento de reconexión.
**Por qué**: a ~2.100 clientes, un corte masivo provocaría un pico simultáneo de reconexiones (thundering herd) que tumbaría el backend; el jitter distribuye los reintentos (RN-HB-05).
**Alternativa considerada**: reintento a intervalo fijo → sincroniza a todos los clientes en el mismo instante.

### D3 — Replay ordenado en cliente + deduplicación por `event_id` en backend (exactly-once lógico)
**Decisión**: el cliente drena el buffer en orden; el backend deduplica por `event_id` contra la persistencia. La garantía es exactly-once **lógico** (at-least-once en transporte + idempotencia por id), no exactly-once de red.
**Por qué**: la red no garantiza exactly-once; la idempotencia por `event_id` en el backend convierte un replay at-least-once en exactly-once lógico, sin pérdida ni duplicados (RN-HB-03).
**Alternativa considerada**: confiar en que el cliente no reenvíe duplicados → frágil ante reconexiones parciales; el backend debe ser la autoridad de deduplicación.

### D4 — Política por duración: 5 min como umbral (heartbeats como reloj)
**Decisión**: usar la ausencia de heartbeats (/5s de C-10) como reloj del corte; < 5 min → replay sin pérdida; > 5 min → evento crítico al reconectar.
**Por qué**: el heartbeat ya es la prueba de vida (RN-HB-01); su ausencia prolongada (> 5 min) es información relevante para el panel (RN-HB-04, RN-EV-04). El umbral de 5 min viene del dominio.
**Alternativa considerada**: no distinguir por duración → se pierde la señal de que algo anómalo (corte largo) ocurrió.

### D5 — El evento crítico por corte largo es señal, no sanción (L2.5)
**Decisión**: el evento crítico de "corte de conectividad prolongado" se emite como señal para el panel; ninguna sanción automática se deriva.
**Por qué**: L2.5 y RN-RV-07 — ninguna sanción es automática; además, la resiliencia existe precisamente para no penalizar por mala red.
**Alternativa considerada**: ninguna (regla dura del dominio).

## Arquitectura de la resiliencia (frontend / transport)

```
[productor de eventos — C-11]           [transport — C-14]                 [backend — C-10]
   evento ──────────────────────►  persiste en buffer IndexedDB (circular)
                                    │   WS arriba → envía
                                    │   WS caído → solo bufferiza
                                    │
   (WS cae)                         ├─ reconexión: backoff exp. + jitter 20%
                                    │   handshake(session_id, JWT, last_event_id) ──► backend
                                    │                                       reenvía eventos > last_event_id
                                    ├─ drena buffer EN ORDEN ────────────► dedup por event_id (exactly-once lógico)
                                    │
                                    └─ política por duración (reloj = heartbeats /5s):
                                          < 5 min → replay sin pérdida
                                          > 5 min → evento crítico al reconectar (señal al panel, NO sanción)
```

| Componente | Responsabilidad | Notas |
|------------|-----------------|-------|
| Buffer IndexedDB | persistir eventos resistiendo cortes | circular, sobrevive refresh (D1) |
| Reconnector | backoff exp. + jitter 20%, handshake con `last_event_id` | evita thundering herd (D2) |
| Replay/dedup | drenar en orden; dedup por `event_id` en backend | exactly-once lógico (D3) |
| Política de corte | clasificar por duración vía ausencia de heartbeats | < 5 min / > 5 min (D4); evento crítico = señal (D5) |

## Risks / Trade-offs

- **[Pérdida de eventos ante refresh/cierre]** → Mitigación: D1 — buffer en IndexedDB, no en memoria.
- **[Thundering herd tras corte masivo]** → Mitigación: D2 — backoff exponencial + jitter 20%.
- **[Duplicados en el replay]** → Mitigación: D3 — deduplicación por `event_id` en el backend (exactly-once lógico).
- **[Penalizar al estudiante por mala red]** → Mitigación: D5 — el evento por corte largo es señal, no sanción; la resiliencia evita el falso positivo de "ausencia".
- **[Buffer ilimitado en cortes muy largos]** → Mitigación: buffer circular acotado; el corte > 5 min ya queda registrado como evento crítico.
- **Trade-off aceptado**: exactly-once **lógico** (no de red) — se acepta at-least-once en transporte porque la idempotencia por `event_id` lo resuelve sin protocolo de red costoso.

## Migration Plan

No hay sistema previo. Puesta en marcha:
1. Implementar el buffer circular en IndexedDB y cablear la escritura de cada evento antes del envío.
2. Implementar el reconnector con backoff exponencial + jitter 20% y el handshake con `last_event_id` (contra el gancho de C-10).
3. Implementar el drenaje ordenado del buffer y verificar la deduplicación por `event_id` contra la persistencia de C-10.
4. Implementar la política por duración (reloj = heartbeats /5s) y la emisión del evento crítico por corte > 5 min.
5. Verificar cero pérdida en cortes < 5 min y la señal crítica en cortes > 5 min.

**Rollback**: al ser frontend con buffer local, un fallo se revierte sin pérdida porque los eventos siguen en IndexedDB hasta confirmarse; el contrato y la persistencia de C-10 no se ven afectados.

## Open Questions

Las que este change **cierra**:
- ¿Cómo se garantiza cero pérdida ante cortes cortos? → `indexeddb-event-buffer` + `ordered-replay-dedup`.
- ¿Cómo se evita el thundering herd al reconectar? → `reconnect-backoff`.
- ¿Cómo se distingue un corte corto de uno largo y qué se hace? → `outage-duration-policy`.

Las que **quedan fuera** (otros changes):
- Canal WS, contrato de evento, validación de firma, persistencia y consulta por `last_event_id` → C-10.
- Producción de los eventos protegidos → C-11.
- Fan-out a paneles → C-10 / C-15.
