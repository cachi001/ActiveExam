## Context

Estado actual del cliente (verificado en el código):

- `frontend/src/lib/store.ts`: store Zustand con `create()` SIN `persist`. Persiste a
  mano solo `examenActivo`, `proctoringSessionId` y `proctoringSessionCreadaEn` en
  `sessionStorage`. `principal`, `rol` y el resto son en memoria.
- `frontend/src/lib/authStore.ts`: SEGUNDO store con `status`, `principal`, `token`.
  El token se restaura de `provider.getToken()`; el auth SÍ sobrevive a un reload,
  pero el `principal` queda duplicado entre los dos stores.
- Pantallas (p. ej. `AdminDashboard.tsx`): `api.x().then(set).finally(()=>setCargando(false))`
  SIN `.catch`. En error, el estado queda en su valor inicial vacío y se muestra como
  dato → el "0 exámenes" en prod.

## Goals / Non-Goals

**Goals:**
- Recargar/navegar NO pierde la sesión ni parpadea el rol/principal.
- Un fetch fallido NUNCA se muestra como dato (ni "0", ni lista vacía); hay reintento.
- Navegar entre páginas no vuelve a pedir todo en frío (se sirve lo último bueno).
- Una sola fuente de verdad del principal.

**Non-Goals:**
- NO introducir un framework de estado servidor pesado si un hook propio alcanza
  (decisión abierta abajo; preferir liviano).
- NO persistir biometría en el cliente (regla dura; se mantiene).
- NO tocar el backend.
- NO rediseñar el auth (el token ya se restaura); solo unificar el principal.

## Decisions

- **D1 — Persistencia selectiva con `persist` de Zustand.** Envolver el store con el
  middleware `persist` y una función `partialize` que persista SOLO un allowlist
  seguro (`rol`, preferencias de UI; el `principal` sale de authStore). `sessionStorage`
  vs `localStorage`: elegir en apply según si la sesión debe sobrevivir al cierre de
  pestaña (probable `sessionStorage`, coherente con lo actual). **Guardrail**: la
  `partialize` es un allowlist explícito; biometría y tokens NUNCA entran.
- **D2 — Principal con única fuente de verdad = `authStore`.** `store.ts` deja de
  duplicar `principal`; las pantallas lo leen de authStore (o un selector unificado).
  Elimina el riesgo de inconsistencia.
- **D3 — Contrato de carga `AsyncState<T>`.** Tipo `{ status: 'loading'|'error'|'ready', data?, error? }`
  (o un hook `useAsyncData`) que las pantallas usan en vez de `[]`+`cargando` sueltos.
  Regla: mientras `loading` se muestra placeholder; en `error` se muestra estado de
  error + reintento; un `0` real solo se pinta con `status==='ready' && data.length===0`.
- **D4 — Cache liviano de lectura.** Un cache en memoria por clave de query (con
  "stale-while-revalidate": servir lo último bueno y revalidar en background) para que
  navegar no refetchee en frío. Evaluar en apply si alcanza un hook propio o conviene
  una lib mínima; preferir propio para no sumar peso al bundle (< 500 KB objetivo).
- **D5 — Migración incremental.** Se arregla primero el patrón (hook/contrato) y se
  migran las pantallas afectadas; el `AdminDashboard` (stat "0") es el caso de prueba.

## Risks / Trade-offs

- **Persistir estado viejo tras un deploy** (shape cambia) → versionar la clave de
  persist (`version` + `migrate` de Zustand) para descartar estado incompatible.
- **Fuga de datos sensibles** si el allowlist se amplía sin cuidado → la `partialize`
  es la única puerta; test que verifique que biometría/token NO se persisten.
- **Cache sirviendo datos viejos** → stale-while-revalidate + invalidación en mutación;
  no cachear lo que debe ser siempre fresco (p. ej. estado de rendición en vivo).
- **Doble fuente del principal durante la migración** → hacer D2 de una y borrar el
  campo duplicado, no dejar los dos conviviendo.

## Moodle — integración con el campus real (agregado a C-73)

### Contexto (verificado en el código)

El write-back de nota a Moodle **ya está construido** (C-69) y no hay que reescribirlo:

- `backend/app/infrastructure/moodle/client.py` — `MoodleRestClient`: `write_grade`
  vía `core_grades_update_grades` + `lookup_userid_by_idnumber` / `lookup_userid_by_email`.
- `backend/app/application/moodle/writeback_service.py` — `MoodleWritebackService`:
  estado idempotente (pendiente/enviado/fallido), audit log, sanitiza el token, reintenable.
- `backend/app/application/proctoring/finalizar_con_writeback.py` — dispara el write-back
  al finalizar la sesión.
- Cableado en `main_slim.py`: si `settings.moodle_base_url` está vacío el write-back se
  apaga solo y la nota queda `persistir_nota_pendiente` para sync manual del admin.

Lo que falta NO es el servicio: es **(a)** operarlo contra el campus real
(`campustest.frm.utn.edu.ar`) y **(b)** las **funciones de lectura** que el proctoring
necesite traer DE Moodle.

### Decisiones

- **DM1 — No reescribir el write-back.** Se reutiliza `MoodleWritebackService` tal cual;
  esta etapa solo lo configura contra el campus real y lo valida E2E. Cualquier cambio
  al servicio que surja de la validación se hace mínimo y con test.
- **DM2 — Config por entorno + secreto.** `MOODLE_BASE_URL` / `MOODLE_WS_TOKEN` /
  `courseid` / `cmid` desde el secret manager. El token nunca en repo/imagen/log/cliente.
  Degradación segura si no hay URL (comportamiento actual, se preserva).
- **DM3 — L2.5 intacto.** Se sincroniza SOLO la nota académica (respuestas correctas).
  El score/flags de proctoring van a revisión humana aparte; nunca se escriben como nota
  ni penalizan automáticamente. El write-back actual ya cumple esto (docstring del servicio).
- **DM4 — Lectura server-side, dato no confiable.** Las funciones de lectura nuevas usan
  el token server-side y validan la respuesta de Moodle en el borde (regla dura #6). El
  cliente nunca invoca la WS.

### Pregunta abierta (se resuelve en la sesión en vivo del campus)

**¿Qué funciones de lectura de Moodle necesita el proctoring?** Candidatos a validar/decidir
explorando el campus real con Playwright y las credenciales del owner:

- **Padrón / participantes de un curso** (`core_enrol_get_enrolled_users`): inscripciones
  reales, para gatear quién puede rendir (¿reemplaza o complementa la matriculación por
  código `inscribirmePorCodigo`?).
- **Disponibilidad de la actividad de examen** (apertura/cierre del quiz/assignment):
  alimenta el pendiente del owner "botón Rendir gateado por apertura/cierre".
- **Identidad del participante** (perfil / idnumber / email / foto): reforzar el mapeo de
  identidad y, potencialmente, la verificación biométrica contra la foto institucional.
- **Ítems de calificación del curso** (`core_grades_get_grades` / grade items): confirmar
  el destino `courseid`/`cmid` por examen contra la estructura real del curso.

El set final y sus WS exactas quedan para la exploración en vivo; recién ahí se escriben
como tareas concretas.
