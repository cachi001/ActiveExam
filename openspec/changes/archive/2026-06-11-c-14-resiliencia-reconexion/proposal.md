# Proposal — C-14 `resiliencia-reconexion`

> **Naturaleza del change**: núcleo de monitoreo en tiempo real, governance **ALTO**. Frontend / transport. Implementa la **resiliencia de red sin pérdida** sobre el canal WS del estudiante de C-10: buffer local en IndexedDB, reconexión con backoff y replay deduplicado (exactly-once lógico). Garantiza que una conexión inestable no produzca pérdida de evidencia ni penalice injustamente al estudiante.

## Why

El estudiante con conexión inestable es un escenario real y frecuente. Si los eventos se pierden cuando cae el WebSocket, dos cosas malas pasan: se pierde evidencia (rompe RN-CC-08, "cero pérdida de eventos confirmados") y se penaliza injustamente a quien tiene mala red (un corte parecería "rostro ausente prolongado"). El sistema debe ser **resiliente por diseño** (RN-HB-02…RN-HB-05): los eventos persisten localmente y se reenvían al reconectar, sin pérdida ni duplicación.

El Flujo 5 fija la mecánica: al caer el WS, los eventos van a un buffer circular en IndexedDB; el cliente reconecta con **backoff exponencial + jitter 20%** (para evitar el "thundering herd" de miles de clientes reconectando a la vez); el handshake de reconexión envía `last_event_id`; el backend reenvía los eventos faltantes; el cliente drena su buffer en orden y el backend deduplica por `event_id` (**exactly-once lógico**). Cortes < 5 min no generan pérdida; cortes > 5 min generan un evento crítico al reconectar (RN-HB-03, RN-HB-04, RN-EV-04).

Este change construye **esa resiliencia con calidad de producción**, apoyándose en el gancho `last_event_id` y la consulta de eventos faltantes que **C-10 ya expone**.

## What Changes

Construye la **capa de resiliencia del transporte del estudiante** sobre el canal WS de C-10.

- **Buffer IndexedDB**: los eventos se persisten localmente en un buffer circular resistente a cortes; si el WS cae, los eventos siguen guardándose sin pérdida (RN-HB-02).
- **Reconexión con backoff exponencial + jitter**: ante la caída del WS, el cliente reconecta con backoff exponencial y jitter del 20% para evitar el thundering herd de reconexiones simultáneas (RN-HB-05).
- **Handshake de reconexión con `last_event_id`**: el cliente reconecta enviando el `last_event_id` (gancho expuesto por C-10); el backend reenvía los eventos faltantes posteriores a ese id.
- **Drenaje del buffer en orden con deduplicación (exactly-once lógico)**: el cliente drena el buffer local en orden; el backend deduplica por `event_id`, garantizando exactly-once lógico — ni pérdida ni duplicados (RN-HB-03).
- **Política de cortes por duración**: cortes < 5 min → **sin pérdida** (replay completo del buffer); cortes > 5 min → se emite un **evento crítico** al reconectar (RN-HB-04, RN-EV-04).

**El sistema NUNCA sanciona automáticamente (L2.5, RN-RV-07)**: el evento crítico por corte prolongado es una señal para el panel, no una penalización; la decisión es siempre humana. El objetivo de la resiliencia es precisamente **no penalizar injustamente** por problemas de red.

## Capabilities

### New Capabilities

- `indexeddb-event-buffer`: el buffer circular local en IndexedDB que persiste los eventos resistiendo cortes del WS, de modo que ninguna caída de red provoque pérdida.
- `reconnect-backoff`: la reconexión con backoff exponencial + jitter del 20% que evita el thundering herd, y el handshake de reconexión con `last_event_id`.
- `ordered-replay-dedup`: el drenaje del buffer en orden y la deduplicación por `event_id` que garantizan exactly-once lógico (ni pérdida ni duplicados) sobre el replay de eventos faltantes.
- `outage-duration-policy`: la política por duración del corte — < 5 min sin pérdida, > 5 min evento crítico al reconectar.

### Modified Capabilities

(Ninguna — no existen specs de dominio previas en `openspec/specs/` que este change modifique. Consume el canal WS y el gancho `last_event_id` de C-10 como dependencia, no los modifica.)

## Impact

- **Dependencias entrantes**: `C-10` (consume el canal WS del estudiante, el handshake con `last_event_id` y la consulta de eventos posteriores a `last_event_id` que C-10 expone; la deduplicación exactly-once se cierra contra la persistencia de C-10).
- **Complementa**: C-11 (los eventos producidos por los detectores son los que este buffer protege ante cortes) y la cadena de custodia de C-12 (al no perder eventos confirmados, sostiene RN-CC-08).
- **Actores/sistemas afectados**: estudiante con conexión inestable (principal beneficiario — no se penaliza por su red), backend (reenvía faltantes y deduplica), panel (recibe el evento crítico por corte prolongado como señal, no como sanción).
- **Riesgo principal**: thundering herd de miles de clientes reconectando tras un corte de red masivo — mitigado por el backoff exponencial + jitter 20% (RN-HB-05).
- **Garantía clave**: cero pérdida de eventos confirmados (RN-CC-08) bajo cortes < 5 min, con exactly-once lógico.
