## Why

Durante un examen real en Railway, `proctoring_event` y `proctoring_biometria` quedan con 0 filas y `finalizada_en` es siempre `null` — el pipeline de proctoring detecta anomalías y la sesión se crea, pero ningún dato secundario se persiste. El diagnóstico identificó 4 causas raíz concretas, todas corregibles sin cambios de esquema DB ni nuevas migraciones.

## What Changes

- **Fix #1 — schema extra='forbid' rechaza `screenshot_sha256_cliente`**: el payload que construye `handleEvent` en `useExamProctoring.ts` incluye `screenshot_sha256_cliente`, pero `IngestEventoIn` tiene `extra='forbid'` y lo rechaza con 422. El backend devuelve error, el catch lo traga, y el evento se pierde. Fix: agregar el campo `screenshot_sha256_cliente: str | None` a `IngestEventoIn` (campo ya calculado por el cliente para la cadena de custodia).
- **Fix #2 — error de red tragado en silencio**: el catch en `handleEvent` (~línea 225) no loguea ni reintenta ante un 422. Fix: loguear con `console.error` el status y el body del error para facilitar diagnóstico en prod; el buffer ya persiste el evento para el drain, por lo que el comportamiento de resiliencia es correcto una vez que el 422 desaparece.
- **Fix #3 — ciclo de vida de la sesión de proctoring**: la sesión se crea en `useExamProctoring` (paso 5 — examen en vivo), pero la verificación biométrica ocurre en el paso 3 (`Biometria.tsx`). En ese momento `proctoringSessionId` es siempre `null` → la biometría nunca se persiste. Fix: crear la sesión de proctoring al inicio del flujo del alumno (al montar `ExamenLayout` o similar, antes del paso biométrico) para que el `proctoringSessionId` exista cuando el alumno complete la verificación.
- **Fix #4 — `finalizada_en` nunca se setea**: no existe un endpoint de finalización de sesión ni una llamada desde `Cierre.tsx`. Fix: agregar `PATCH /proctoring/sessions/{id}/finalizar` en el backend y llamarlo desde `Cierre.tsx` al renderizar.
- **Fix #5 — Cierre.tsx y "Sesiones grabadas" muestran datos locales**: `Cierre.tsx` lee `anomaliasVivo` del store Zustand (que no se puebla porque `pushAnomalia()` no se llama en `handleEvent`). Fix: que `Cierre.tsx` consulte el backend (`GET /proctoring/sessions/{id}`) para mostrar el conteo real de eventos y score persistido.

## Capabilities

### New Capabilities
- `proctoring-session-lifecycle`: ciclo de vida correcto de la sesión de proctoring — creación anticipada al inicio del flujo del alumno, finalización explícita en Cierre, endpoint `PATCH /sessions/{id}/finalizar`.

### Modified Capabilities
- `exam-proctoring-resilience`: el schema `IngestEventoIn` acepta el campo `screenshot_sha256_cliente`; el catch de eventos loguea el error en lugar de tragarlo.

## Impact

- **Backend**: `backend/app/presentation/api/v1/proctoring/events/schemas.py` (agregar campo), `backend/app/presentation/api/v1/proctoring/sessions/router.py` (agregar endpoint finalizar), `backend/app/presentation/api/v1/proctoring/sessions/schemas.py` (schema FinalizarOut), `backend/app/application/proctoring/session_service.py` (función `finalizar_sesion`).
- **Frontend**: `frontend/src/proctoring/useExamProctoring.ts` (loguear error, no cambiar resiliencia), `frontend/src/screens/Cierre.tsx` (GET sesión del backend para conteos reales), `frontend/src/lib/api.ts` (agregar `finalizarSesionProctoring`), y el punto de montaje del flujo del alumno donde se crea la sesión de proctoring anticipadamente.
- **Tests**: tests de integración para el nuevo endpoint `finalizar` y para el campo `screenshot_sha256_cliente` en ingestión de eventos.
- **No hay cambios de esquema DB ni migraciones**: los modelos ORM no cambian; `finalizada_en` ya existe en `proctoring_session`.
