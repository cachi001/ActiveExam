## Why

Hoy el cliente no persiste su estado ni maneja bien la carga de datos, y eso se ve
en producción:

- El store de Zustand (`frontend/src/lib/store.ts`) usa `create()` **sin** el
  middleware `persist`. Solo guarda a mano `examenActivo` y `proctoringSessionId`
  en `sessionStorage`. Todo lo demás (rol, principal, listas) vive en memoria y se
  re-fetchea de cero en cada navegación/recarga: parece que "no se usa Zustand".
- Hay **dos fuentes de verdad del principal** (`store.ts` y `authStore.ts`), que
  pueden quedar inconsistentes.
- Las pantallas cargan datos en `useEffect` sin `.catch`: si el fetch falla (p. ej.
  el token todavía no está listo tras un F5), la promesa rechaza, el `finally`
  apaga el spinner y el estado queda en su valor inicial vacío. **Bug real en prod:
  la stat card mostró "0 exámenes" habiendo uno** — un fetch fallido se renderizó
  como un cero legítimo, no como un error.

Es transversal: afecta TODAS las páginas y es la base sobre la que apoyan los
próximos changes (disponibilidad de examen, auditoría, estadísticas). Arreglarlo
primero hace todo lo demás menos frágil.

## What Changes

- Persistir el estado de sesión del cliente que es seguro persistir (rol, principal,
  preferencias de UI) para que recargar NO pierda la sesión ni parpadee, con una
  ÚNICA fuente de verdad del principal.
- Introducir un contrato de carga de datos resiliente: cada pantalla distingue
  `cargando / error / vacío-real / cargado`. Un fetch fallido nunca se muestra como
  un dato (nunca "0" ni lista vacía silenciosa); ofrece reintento.
- Cache liviano de queries para que navegar entre páginas no vuelva a pedir todo
  en frío (se sirve lo último bueno mientras revalida).
- Mantener la regla dura: **NUNCA persistir datos biométricos en el cliente**
  (el embedding ya está fuera; el `referencia_id` opaco es lo único que puede vivir).
- **Moodle (bundle, "lo que se pueda juntar se junta")**: operar el write-back de nota
  —que YA existe (C-69)— contra el **campus real** (`campustest.frm.utn.edu.ar`):
  config por secreto, validación E2E de la sincronización de notas, y una base para las
  **funciones de lectura** que el proctoring necesite traer DE Moodle (definidas en una
  sesión de exploración en vivo). NO se reescribe el write-back; se configura y valida.

## Capabilities

### New Capabilities
- `client-session-persistence`: qué estado del cliente se persiste a través de una
  recarga (rol/principal/UI), con qué almacenamiento, y qué NUNCA se persiste
  (biometría). Única fuente de verdad del principal.
- `resilient-data-loading`: contrato de carga de las pantallas — estados explícitos
  de cargando/error/vacío/cargado, sin errores tragados, con reintento y un cache
  que evita el refetch en frío al navegar.
- `moodle-campus-integration`: operar la integración Moodle contra el campus real —
  config gated por secreto y degradación segura, validación E2E del write-back de nota
  (que ya existe en `moodle-grade-writeback`, C-69), L2.5 (solo nota académica humana),
  y lectura server-side de datos de Moodle (funciones a definir en la sesión en vivo).

### Modified Capabilities
<!-- Sin cambios de requisitos en capabilities existentes: es infraestructura de cliente nueva. -->

## Impact

- `frontend/src/lib/store.ts` (persist middleware + slice persistible), `authStore.ts`
  (única fuente del principal), `frontend/src/lib/api.ts` (cache liviano opcional).
- Pantallas que cargan datos en `useEffect` (AdminDashboard y las demás con el
  patrón `.then(set).finally(...)` sin `.catch`): adoptan el contrato de carga.
- Frontend: sin nuevas dependencias pesadas (persist es de zustand; el cache puede ser
  un hook propio liviano, no una lib nueva salvo que se decida).
- Backend (solo la parte Moodle): NO se reescribe el write-back existente
  (`app/infrastructure/moodle/`, `app/application/moodle/`); se configura contra el campus
  real (env/secreto) y se valida E2E. Las funciones de lectura nuevas se definen en la
  sesión en vivo. `main_slim.py` ya cablea el servicio gated por `MOODLE_BASE_URL`.
- Guardrail de privacidad (Ley 25.326): la clave persistida NO incluye embeddings
  ni descriptores faciales.
