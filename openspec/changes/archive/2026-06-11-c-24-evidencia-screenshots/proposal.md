## Why

Hoy la evidencia automática del sistema es un **clip de video de 5–10 s** por evento severo (RN-CC-01; `07_flujos_principales.md` §EVIDENCIA). Eso cuesta **~2,8 GB por examen (4 clips/estudiante)** en almacenamiento WORM (`14_observabilidad_y_devops.md` §Capacity). Para un proctoring **L2.5** ese volumen es **desproporcionado**: la minimización de datos de la Ley 25.326 y el principio de proporcionalidad (`13_legal_y_cumplimiento_argentina.md`) empujan a capturar lo mínimo necesario para una **revisión humana**, no horas de video.

Este change reemplaza el clip por un **screenshot** (captura de frame único, KB en vez de GB) y define la **cadencia** de captura: **event-driven** (un screenshot al disparar un evento de severidad alta/crítica) **+ heartbeat** (un screenshot periódico de baja frecuencia como línea base, configurable por examen). Es una **decisión de arquitectura** (gobernanza ALTO) que cambia el modelo de evidencia del sistema.

## What Changes

- **BREAKING** — El artefacto de evidencia automática pasa de **clip de video (5–10 s)** a **screenshot (frame único)**. Cambia el tipo de binario, su tamaño (de ~GB a ~KB) y lo que el backend puede re-inferir (detección **estática** sobre el frame, ya no temporal).
- Se ajusta **RN-CC-01**: un evento de severidad **alta/crítica** dispara la captura de un **screenshot**, no de un clip.
- Se añade una **cadencia de captura** con dos disparadores: **event-driven** (por evento severo) y **heartbeat** (periódico, baja frecuencia, configurable por examen) que provee una línea base proporcional.
- La **cadena de custodia se mantiene intacta**: cada screenshot se hashea (SHA-256) + firma (HMAC de sesión) en cliente, se re-hashea/re-valida/re-firma server-side con clave maestra y se deposita en bucket **WORM cifrado** (RN-CC-02/04). La re-inferencia server-side se hace **sobre el frame** (estática), no sobre una secuencia temporal.
- Se acepta explícitamente el **tradeoff L2.5**: un frame fijo **no permite re-inferencia temporal ni re-verificación de liveness/movimiento**; la evidencia es más débil para impugnaciones que requieran contexto temporal. Ver DD en `design.md`.
- Se actualiza el **modelo de costo** de evidencia (`14_observabilidad_y_devops.md`): el volumen por examen cae de ~2,8 GB a unos pocos MB.

## Capabilities

### New Capabilities
- `screenshot-evidence-capture`: captura de un **frame único** (screenshot) como artefacto de evidencia en el cliente (zona no confiable), reemplazando el clip; conserva la cadena de custodia (hash + firma de origen, upload directo por URL firmada).
- `evidence-capture-cadence`: política de **cadencia** de captura — disparador **event-driven** (evento de severidad alta/crítica) **+ heartbeat** periódico de baja frecuencia, configurable por examen.

### Modified Capabilities
- `evidence-capture-upload`: el requisito de captura cambia de **clip de 5–10 s** a **screenshot (frame único)** ante evento de severidad alta/crítica (RN-CC-01); el hash/firma de origen y el upload directo por URL firmada se mantienen, ahora aplicados a la imagen.

## Impact

- **Reglas de negocio**: RN-CC-01 (`05_reglas_de_negocio.md`) — la captura automática produce screenshot, no clip.
- **Flujos**: `07_flujos_principales.md` §EVIDENCIA — el paso "clip 5-10s" pasa a "screenshot".
- **IA/Visión**: `11_ia_y_vision.md` — la re-inferencia server-side deja de ser temporal (1–10 s sobre clip) y pasa a ser **estática sobre el frame**.
- **Capacidad/Costo**: `14_observabilidad_y_devops.md` — el modelo de ~2,8 GB/examen (4 clips/estudiante) cae a MB; el SLI de "subidas de evidencia pesadas" se relaja.
- **Legal**: `13_legal_y_cumplimiento_argentina.md` — mejora la minimización de datos y la proporcionalidad L2.5.
- **Capability existente afectada**: `evidence-capture-upload` (de c-12). NO se editan los archivos de c-12; el delta se modela dentro de este change.
- **Cadena de custodia (c-12)**: `evidence-custody-chain`, `evidence-worm-storage` y `evidence-audit-log` **no cambian su contrato** — siguen aplicando al nuevo binario (imagen). La cuarta etapa (re-inferencia firmada) opera ahora sobre frame estático.
