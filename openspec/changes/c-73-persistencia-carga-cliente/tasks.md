# Tasks — c-73 Persistencia + carga de datos resiliente

> TDD estricto (Three Laws): test que falla → mínimo código → triangular. Sin mocks
> de DB (acá es frontend: usar vitest + testing-library, mockear `api`/`fetch`, no la DB).

## 1. Contrato de carga resiliente (base del stat "0")

- [x] 1.1 Test (RED): un helper/hook `useAsyncData` (o `AsyncState<T>`) expone `status:
      'loading'|'error'|'ready'`; ante rechazo del fetch queda en `error` (no `ready` con dato vacío)
- [x] 1.2 Implementar el helper/hook mínimo para pasar el test
- [x] 1.3 Triangular: éxito con lista → `ready` con data; éxito vacío → `ready` con `[]`;
      fallo → `error` con posibilidad de `retry()`
- [x] 1.4 Test: `retry()` re-dispara el fetch y transiciona `loading → ready/error`

## 2. Arreglar el bug del stat "0" (AdminDashboard como caso de prueba)

- [ ] 2.1 Test (RED): con `api.listarExamenesContenido` rechazando, AdminDashboard NO
      muestra "0" en la stat de Exámenes — muestra estado de error + reintento
- [ ] 2.2 Test: con la lista cargando → placeholder; con éxito y 1 examen → "1"; con
      éxito y 0 → "0" legítimo
- [x] 2.3 Migrar AdminDashboard al contrato de carga (reemplazar `.then(set).finally(...)`
      sin `.catch` por el hook); verificar que ningún camino pinta el vacío inicial como dato
- [ ] 2.4 Inventariar las demás pantallas con el patrón `.then(set).finally(...)` sin
      `.catch` y migrarlas (o listar las que quedan como deuda explícita)

## 3. Persistencia selectiva del store (Zustand `persist`)

- [x] 3.1 Test (RED): tras "recargar" (rehidratar el store desde el storage simulado),
      el `rol` y las preferencias de UI persisten; biometría y token NO aparecen en lo serializado
- [x] 3.2 Envolver el store con `persist` + `partialize` allowlist (rol + UI); elegir
      `sessionStorage`/`localStorage` y documentar por qué
- [x] 3.3 Test: `partialize` es un allowlist explícito — agregar un campo sensible al
      state NO lo filtra al storage (guardrail de privacidad, Ley 25.326)
- [x] 3.4 Versionar la clave (`version` + `migrate`): estado de shape viejo se descarta
      sin romper; test de que un blob incompatible no crashea el arranque

## 4. Única fuente de verdad del principal

- [x] 4.1 Test: las pantallas leen el principal desde `authStore` (fuente única); no
      queda una copia divergente en `store.ts`
- [x] 4.2 Quitar la duplicación de `principal` (unificar en authStore o un selector);
      migrar los consumidores
- [x] 4.3 Test de regresión: login/logout limpia el estado del usuario anterior (no se
      hereda rol/principal/enrollment entre usuarios en el mismo browser)

## 5. Cache liviano de lectura (stale-while-revalidate)

- [x] 5.1 Test (RED): volver a una query ya cargada sirve lo último bueno de inmediato
      y dispara una revalidación en background
- [x] 5.2 Implementar el cache por clave (hook propio liviano; evaluar y JUSTIFICAR si
      se suma una lib mínima, respetando el objetivo de bundle < 500 KB)
- [x] 5.3 Test: el estado que debe ser fresco (rendición/supervisión en vivo) NO se
      sirve del cache stale
- [x] 5.4 Invalidación en mutación: tras una escritura, la query afectada se revalida

## 6. Verificación y cierre

- [ ] 6.1 `tsc --noEmit` del frontend sin errores
- [ ] 6.2 Suite de frontend completa en verde (vitest), incluidos los tests nuevos
- [ ] 6.3 E2E manual: recargar en varias páginas mantiene sesión sin parpadeo; matar la
      red y entrar a AdminDashboard muestra ERROR (no "0"); navegar ida/vuelta no
      refetchea en frío
- [ ] 6.4 `openspec validate c-73-persistencia-carga-cliente` en verde

## 7. Moodle — configurar y validar el write-back contra el campus real

> El write-back ya existe (C-69); acá se OPERA contra el campus real. Tests de backend
> con DB real (no mocks de DB). El envío real a Moodle se prueba contra `campustest`.

- [ ] 7.1 Documentar/parametrizar la config del campus real (`MOODLE_BASE_URL`,
      `MOODLE_WS_TOKEN`, `courseid`, `cmid`) desde el secret manager / entorno; confirmar
      que el token no aparece en repo/imagen/logs (grep de guardrail)
- [ ] 7.2 Test (RED→GREEN): con `MOODLE_BASE_URL` vacío, la finalización persiste la nota
      en estado sincronizable y NO rompe ningún flujo (degradación segura ya existente, fijar contrato)
- [ ] 7.3 Validación E2E contra `campustest.frm.utn.edu.ar` con un usuario de prueba: la
      nota calculada llega a la libreta del usuario correcto (idnumber→email); el intento
      queda auditado sin el token
- [ ] 7.4 Verificar el caso de identidad no resoluble contra el campus real (no escribe a
      un usuario arbitrario; queda fallido/pendiente de revisión)
- [ ] 7.5 Confirmar L2.5: lo sincronizado es solo la nota académica (respuestas correctas);
      ningún flag/score de proctoring se escribe como nota

## 8. Moodle — funciones de lectura (definir en la sesión en vivo)

> BLOQUEADA por la exploración en vivo del campus (owner presente + credenciales +
> Playwright). Recién ahí se convierten en tareas concretas con sus WS exactas.

- [ ] 8.1 Sesión en vivo: explorar `campustest` con Playwright y mapear las Web Services
      disponibles (padrón/participantes, disponibilidad de examen, identidad, grade items)
- [ ] 8.2 Decidir con el owner qué funciones de lectura necesita el proctoring y priorizarlas
- [ ] 8.3 Reescribir 8.x como tareas concretas (por función elegida) con TDD y dato de
      Moodle tratado como no confiable (validado en el borde, server-side)
