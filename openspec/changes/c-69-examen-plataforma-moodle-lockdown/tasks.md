# Tasks — C-69 `examen-plataforma-moodle-lockdown`

> Construir la experiencia de rendición REAL dentro de la plataforma: quitar toasts de eventos, modelar examen+preguntas en la DB, importar Moodle XML, lockdown de pantalla completa y **write-back de la nota a Moodle** (REST WS `core_grades_update_grades`, server-side).
>
> **Reglas duras**: TDD estricto (RED→GREEN→TRIANGULATE→REFACTOR) en cada grupo. Tests SIN mocks de DB (DB real / contenedor efímero). Pydantic `extra='forbid'`. snake_case en Python, PascalCase en componentes React. NO buildear ni commitear sin pedido. L2.5: nada sanciona automático. Cliente = sensor no confiable: la opción correcta NUNCA viaja al cliente.
>
> **Cada tarea está Done cuando**: el test correspondiente está verde (test-first) y, donde aplica, la verificación manual descrita pasa.

## 1. Quitar toasts de eventos al alumno (capability `student-exam-rendering`) — empezar por acá (bajo riesgo, sin DB)

- [ ] 1.1 RED: test del componente `Examen.tsx` que verifica que, ante un nuevo evento de proctoring en `eventos`, NO se invoca `toast.show` para ese evento; Done: test falla contra el código actual
- [ ] 1.2 GREEN: eliminar el `useEffect` de toasts por evento (`Examen.tsx` ~líneas 107-122), el `toastedIds` ref y el mapa `SEV_TOAST`; quitar el `useToast` si queda sin uso; Done: test 1.1 verde
- [ ] 1.3 TRIANGULATE: test que confirma que la detección/score sigue intacta (el evento se sigue registrando en el panel lateral y `addScore`/streaming server-side no se tocan); Done: test verde con un segundo evento de severidad distinta
- [ ] 1.4 Verificación: render del examen con eventos simulados → no aparece ningún toast por evento; el panel "Señales de integridad" y el score siguen actualizándose; Done: verificado

## 2. Modelo de examen de contenido en la DB (capability `exam-content-model`)

- [ ] 2.1 RED: tests de dominio (entidades examen-contenido / pregunta / opción) — integridad: `multichoice` exige ≥2 opciones y exactamente 1 correcta; `truefalse` exige exactamente 2 con 1 correcta; pregunta inválida → error de validación de dominio; Done: tests fallan sin la entidad
- [ ] 2.2 GREEN: implementar entidades + validaciones de dominio (snake_case); Done: tests 2.1 verdes
- [ ] 2.3 RED: test de repositorio contra **DB real / contenedor efímero** (sin mock) — persistir y recuperar un examen de contenido con preguntas/opciones conservando la marca de correcta server-side; Done: test falla sin migración/repo
- [ ] 2.4 GREEN: migración Alembic **aditiva** rama slim `0026_*` (sigue `0025`, patrón de `0023`: tablas nuevas, FK `ON DELETE CASCADE`, índices) + repositorio; Done: test 2.3 verde
- [ ] 2.5 TRIANGULATE: test de `alembic downgrade slim@0025` → dropea sólo las tablas nuevas, no toca las existentes; Done: test/verificación de reversibilidad verde
- [ ] 2.6 REFACTOR: limpiar nombres/duplicación en dominio y repo manteniendo tests verdes; Done: tests verdes

## 3. API de rendición sin filtrar la opción correcta (capability `exam-taking-api`)

- [ ] 3.1 RED: test de la proyección de rendición — dado un examen con opciones, la proyección NO incluye la marca de opción correcta de ninguna opción; Done: test falla sin la proyección
- [ ] 3.2 GREEN: proyección/servicio server-side que excluye la opción correcta + schemas Pydantic `extra='forbid'`; Done: test 3.1 verde
- [ ] 3.3 RED: test de endpoint `/api/v1` de lectura — alumno habilitado obtiene preguntas+opciones en orden estable; examen inexistente → 404; la respuesta no expone la opción correcta; Done: tests fallan sin el endpoint
- [ ] 3.4 GREEN: endpoint de lectura para rendir (orden estable, 404, sin opción correcta); Done: tests 3.3 verdes
- [ ] 3.5 TRIANGULATE: test de orden determinístico (dos requests → mismo orden) y de aislamiento (examen inexistente no filtra datos de otro examen); Done: tests verdes

## 4. Importador de Moodle XML (capability `moodle-xml-import`)

- [ ] 4.1 RED: tests del parser de Moodle XML con fixtures reales — `multichoice` (varias opciones, una correcta) y `truefalse` mapean a enunciado/opciones/correcta; tipos no soportados (`cloze`, `essay`) se OMITEN; XML inválido/vacío → error; Done: tests fallan sin el parser
- [ ] 4.2 GREEN: parser Moodle XML → estructuras de dominio de `exam-content-model` (snake_case); Done: tests 4.1 verdes
- [ ] 4.3 RED: test de servicio de import contra DB real — un XML válido crea un examen de contenido con sus preguntas; devuelve reporte (importadas / omitidas con su tipo) sin abortar ante tipos no soportados; Done: test falla sin el servicio
- [ ] 4.4 GREEN: servicio de import + persistencia + reporte; Done: test 4.3 verde
- [ ] 4.5 RED: test de endpoint de import admin-only — usuario sin rol de admin de exámenes → 403; admin → 201/200 con reporte; schemas `extra='forbid'`; Done: tests fallan sin el endpoint
- [ ] 4.6 GREEN: endpoint admin-only de import (reusar guards `require_roles`/`require_mfa` del patrón de `exams/router.py`); Done: tests 4.5 verdes
- [ ] 4.7 Frontend: acción/pantalla admin para subir el archivo Moodle XML y mostrar el reporte (importadas/omitidas); Done: test de UI o verificación manual del flujo de subida
- [ ] 4.8 TRIANGULATE: test con XML mixto (soportadas + no soportadas) → importa parciales y reporta omitidas; Done: test verde

## 5. Cablear la rendición real en el frontend (capability `student-exam-rendering`)

- [ ] 5.1 RED: test del componente que verifica que `Examen.tsx` renderiza preguntas/opciones provenientes de la API (no de la constante hardcodeada); Done: test falla contra el `PREGUNTA` actual
- [ ] 5.2 GREEN: cliente de API de rendición + reemplazar la const `PREGUNTA` por las preguntas reales; permitir seleccionar una opción por pregunta; Done: test 5.1 verde
- [ ] 5.3 TRIANGULATE: test con un examen de N preguntas → se renderizan todas en orden estable y cada una acepta selección independiente; Done: test verde
- [ ] 5.4 Verificación: rendir un examen real importado de Moodle XML extremo a extremo en el front; Done: verificado

## 6. Lockdown de pantalla completa (capability `exam-fullscreen-lockdown`)

- [ ] 6.1 RED: tests del módulo de enforcement (deps DOM inyectables, patrón de `contextDetectors.ts`) — al iniciar invoca `requestFullscreen`; ante `fullscreen_exited`/`blur`/`visibilitychange=hidden` marca estado "bloqueado"; al volver a fullscreen+visible lo desmarca; Done: tests fallan sin el módulo
- [ ] 6.2 GREEN: módulo `fullscreenLockdown` (p. ej. `frontend/src/proctoring/fullscreenLockdown.ts`) que consume el `FullscreenDetector`/`FocusDetector` existentes SIN modificar su contrato; Done: tests 6.1 verdes
- [ ] 6.3 RED: test de retrocompat — la señal de fullscreen/blur sigue llegando al pipeline de score igual que antes (el enforcement no la rompe); Done: test verde
- [ ] 6.4 RED: test de componente — entrar al examen con gesto fuerza fullscreen; al salir aparece overlay de bloqueo que tapa las preguntas; botón "Volver a pantalla completa" re-invoca `requestFullscreen`; overlay se oculta al volver; Done: tests fallan sin el overlay
- [ ] 6.5 GREEN: integrar el enforcement + overlay de bloqueo en `Examen.tsx` (gesto de inicio dispara fullscreen; overlay reactivo al estado bloqueado); Done: tests 6.4 verdes
- [ ] 6.6 TRIANGULATE: test L2.5 — salidas repetidas de fullscreen bloquean+re-fuerzan y registran señal para el score, pero NO anulan ni cierran la sesión automáticamente; Done: test verde
- [ ] 6.7 GREEN/Doc: degradación honesta cuando el navegador no soporta Fullscreen API (examen no se rompe) + texto en UI que comunica el límite SO (DD-21: no impide minimize del SO); Done: test de degradación verde + texto presente

## 7. Write-back de la nota a Moodle (capability `moodle-grade-writeback`) — server-side, REST WS `core_grades_update_grades`

- [ ] 7.1 RED: tests del servicio de **cálculo de nota académica** contra **DB real / contenedor efímero** (sin mock de DB) — dado un examen de contenido y las respuestas del alumno, calcula la nota a partir de las respuestas correctas server-side; examen sin respuestas / respuestas inválidas → nota acotada definida (p. ej. 0), no error de crash; Done: tests fallan sin el servicio
- [ ] 7.2 GREEN: servicio de cálculo de nota académica (snake_case); Done: tests 7.1 verdes
- [ ] 7.3 RED: tests del **cliente Moodle REST** (`httpx` async) — invoca `core_grades_update_grades` con `courseid`, ítem/`cmid` destino, usuario y nota; el **HTTP de la WS se mockea** (fake server / respuestas HTTP, NUNCA la DB); respuesta OK → éxito; respuesta de error / excepción de Moodle / token inválido → fallo tipado; el token se toma de la config secreta y NO se loguea; schemas Pydantic `extra='forbid'`; Done: tests fallan sin el cliente
- [ ] 7.4 GREEN: cliente Moodle REST server-side sobre `core_grades_update_grades` + schemas `extra='forbid'`; token inyectado desde el secret manager (no embebido); Done: tests 7.3 verdes
- [ ] 7.5 RED: tests del **mapeo de identidad** alumno↔usuario Moodle — resuelve por `idnumber` (default), fallback por email; sin match único → no envía a usuario arbitrario y marca el envío fallido; Done: tests fallan sin el mapeo
- [ ] 7.6 GREEN: resolución de identidad (idnumber default / email fallback); Done: tests 7.5 verdes
- [ ] 7.7 RED: tests del **servicio de write-back con idempotencia/reintentos** contra DB real (HTTP de Moodle mockeado) — persiste estado del envío (`pendiente`/`enviado`/`fallido`); un reintento de una nota ya `enviado` NO duplica el push; fallo de red/transitorio deja el envío reintenable y un reintento reusa la misma nota; Done: tests fallan sin el servicio
- [ ] 7.8 GREEN: migración Alembic **aditiva** (tabla de estado de envío de nota dentro de `0026_*`) + servicio de write-back idempotente con reintentos + persistencia de estado; Done: tests 7.7 verdes
- [ ] 7.9 RED: test de **manejo de error** — Moodle no responde al finalizar el examen → la sesión finaliza igual, la nota queda persistida y el envío en estado fallido reintenable (la finalización NO se bloquea); Done: test falla sin el manejo de error
- [ ] 7.10 GREEN: disparo server-side al **finalizar la sesión** de examen (hook de finalización / job) que calcula la nota y dispara el write-back sin bloquear la finalización; Done: tests 7.9 verdes
- [ ] 7.11 RED: test de **auditoría** — cada intento (éxito/fallo) registra una entrada de audit log con alumno, sesión, nota, destino (`courseid`/ítem), resultado y timestamp; el **token nunca** aparece en el audit log ni en trazas; Done: test falla sin la auditoría
- [ ] 7.12 GREEN: auditoría del envío en el audit log (sin token); Done: test 7.11 verde
- [ ] 7.13 TRIANGULATE — **L2.5 (regla dura #5)**: test que verifica que la nota enviada a Moodle deriva SÓLO de respuestas correctas y NO incorpora ninguna penalización automática derivada del score/flags de proctoring (nota académica y proctoring separados); Done: test verde
- [ ] 7.14 REFACTOR: limpiar nombres/duplicación en cliente, servicios y mapeo manteniendo tests verdes; Done: tests verdes

## 8. Cierre del change

- [ ] 8.1 Documentar en `proposal.md`/`design.md` (ya hecho) y dejar listo para archivar: al archivar, **actualizar DD-20** en `knowledge-base/09_decisiones_y_supuestos.md` (~líneas 109-120) para reflejar que la plataforma ahora SÍ opera el examen vía importación de Moodle XML **y devuelve la nota a Moodle por REST WS `core_grades_update_grades`** (documentar que el retorno de nota de hoy es por REST WS y que **LTI 1.3 + AGS queda como evolución futura**); Done: tarea de archivo anotada y verificada en el archive
- [ ] 8.2 Al archivar, **actualizar la nota de cancelación de c-44** (`openspec/changes/archive/<fecha>-c-44-*-CANCELLED/` + `CHANGES.md` ~línea 21) indicando que su scope fue revivido por c-69; Done: nota actualizada
- [ ] 8.3 Suite completa de tests verde (backend + frontend) de las capabilities tocadas; Done: verde (sin build/commit salvo pedido explícito)
- [ ] 8.4 `openspec validate` del change sin errores; Done: validación verde
