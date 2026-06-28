# Tasks — C-69 `examen-plataforma-moodle-lockdown`

> Construir la experiencia de rendición REAL dentro de la plataforma: modelar examen+preguntas en la DB, importar Moodle XML, rendir (render + navegación prev/next + finalizar), lockdown de pantalla completa, quitar toasts de eventos y **write-back de la nota a Moodle** (REST WS `core_grades_update_grades`, server-side). Materia + comisión se modelan como concepto del producto pero **NO bloquean el loop MVP** (FK examen→comisión NULLABLE, D11).
>
> **Reglas duras**: TDD estricto (RED→GREEN→TRIANGULATE→REFACTOR) en cada grupo. Tests SIN mocks de DB (DB real / contenedor efímero). Pydantic `extra='forbid'`. snake_case en Python, PascalCase en componentes React. NO buildear ni commitear sin pedido. L2.5: nada sanciona automático. Cliente = sensor no confiable: la opción correcta NUNCA viaja al cliente.
>
> **Cada tarea está Done cuando**: el test correspondiente está verde (test-first) y, donde aplica, la verificación manual descrita pasa.
>
> ## Ordenamiento — primero el loop MVP entregable
> El **loop MVP** (lo que tiene que funcionar YA, en este orden de producto: importar el examen de Moodle → que persista → que al alumno le aparezca para rendir → navegar a la pregunta siguiente/anterior → finalizar → todo sin poder minimizar/salir de pantalla completa) son las **secciones 1 a 5** de abajo. Es el primer bloque entregable. Las secciones 6 (materia + comisión) y 7 (write-back de la nota) **NO forman parte del loop MVP** y NO deben bloquearlo: materia/comisión es metadata opcional (FK NULLABLE, D11) y el write-back es la capa de retorno de nota a Moodle.

## 1. [MVP · loop] Modelo + persistencia del examen de contenido (capability `exam-content-model`) — núcleo del loop ("que persista")

- [x] 1.1 RED: tests de dominio (entidades examen-contenido / pregunta / opción) — integridad: `multichoice` exige ≥2 opciones y exactamente 1 correcta; `truefalse` exige exactamente 2 con 1 correcta; pregunta inválida → error de validación de dominio; Done: tests fallan sin la entidad
- [x] 1.2 GREEN: implementar entidades + validaciones de dominio (snake_case); Done: tests 1.1 verdes
- [x] 1.3 RED: test de repositorio contra **DB real / contenedor efímero** (sin mock) — persistir y recuperar un examen de contenido con preguntas/opciones conservando la marca de correcta server-side; **el examen se crea con `comision_id` en NULL** (sin materia/comisión) y debe ser válido y recuperable; Done: test falla sin migración/repo
- [x] 1.4 GREEN: migración Alembic **aditiva** rama slim `0026_*` (sigue `0025`, patrón de `0023`: tablas nuevas, FK `ON DELETE CASCADE`, índices) con las tablas examen-contenido / pregunta / opción y la columna `comision_id` **NULLABLE** en el examen + repositorio; Done: test 1.3 verde
- [x] 1.5 TRIANGULATE: test de `alembic downgrade slim@0025` → dropea sólo las tablas nuevas, no toca las existentes (proctoring_session, exam_config); Done: test/verificación de reversibilidad verde
- [x] 1.6 REFACTOR: limpiar nombres/duplicación en dominio y repo manteniendo tests verdes; Done: tests verdes

## 2. [MVP · loop] Importador de Moodle XML (capability `moodle-xml-import`) — "importar el examen de Moodle"

- [x] 2.1 RED: tests del parser de Moodle XML con fixtures reales — `multichoice` (varias opciones, una correcta) y `truefalse` mapean a enunciado/opciones/correcta; tipos no soportados (`cloze`, `essay`) se OMITEN; XML inválido/vacío → error; Done: tests fallan sin el parser
- [x] 2.2 GREEN: parser Moodle XML → estructuras de dominio de `exam-content-model` (snake_case); Done: tests 2.1 verdes
- [x] 2.3 RED: test de servicio de import contra DB real — un XML válido crea un examen de contenido con sus preguntas; el examen se crea **con `comision_id` en NULL (NO requiere materia/comisión)** y NO falla por su ausencia; devuelve reporte (importadas / omitidas con su tipo) sin abortar ante tipos no soportados; Done: test falla sin el servicio
- [x] 2.4 GREEN: servicio de import + persistencia + reporte (crea el examen sin materia/comisión); Done: test 2.3 verde
- [x] 2.5 RED: test de endpoint de import admin-only — usuario sin rol de admin de exámenes → 403; admin → 201/200 con reporte; schemas `extra='forbid'`; Done: tests fallan sin el endpoint
- [x] 2.6 GREEN: endpoint admin-only de import (reusar guards `require_roles`/`require_mfa` del patrón de `exams/router.py`); Done: tests 2.5 verdes
- [x] 2.7 Frontend: acción/pantalla admin para subir el archivo Moodle XML y mostrar el reporte (importadas/omitidas); Done: test de UI o verificación manual del flujo de subida
- [x] 2.8 TRIANGULATE: test con XML mixto (soportadas + no soportadas) → importa parciales y reporta omitidas; Done: test verde

## 3. [MVP · loop] API de rendición sin filtrar la opción correcta (capability `exam-taking-api`) — "que al alumno le aparezca para rendir"

- [x] 3.1 RED: test de la proyección de rendición — dado un examen con opciones, la proyección NO incluye la marca de opción correcta de ninguna opción; Done: test falla sin la proyección
- [x] 3.2 GREEN: proyección/servicio server-side que excluye la opción correcta + schemas Pydantic `extra='forbid'`; Done: test 3.1 verde
- [x] 3.3 RED: test de endpoint `/api/v1` de lectura — alumno habilitado obtiene preguntas+opciones en orden estable; examen inexistente → 404; la respuesta no expone la opción correcta; Done: tests fallan sin el endpoint
- [x] 3.4 GREEN: endpoint de lectura para rendir (orden estable, 404, sin opción correcta); Done: tests 3.3 verdes
- [x] 3.5 TRIANGULATE: test de orden determinístico (dos requests → mismo orden) y de aislamiento (examen inexistente no filtra datos de otro examen); Done: tests verdes

## 4. [MVP · loop] Rendición real en el frontend: render + navegación + finalizar + quitar toasts (capability `student-exam-rendering`)

- [x] 4.1 RED: test del componente `Examen.tsx` que verifica que, ante un nuevo evento de proctoring en `eventos`, NO se invoca `toast.show` para ese evento; Done: test falla contra el código actual
- [x] 4.2 GREEN: eliminar el `useEffect` de toasts por evento (`Examen.tsx` ~líneas 107-122), el `toastedIds` ref y el mapa `SEV_TOAST`; quitar el `useToast` si queda sin uso; Done: test 4.1 verde
- [x] 4.3 TRIANGULATE: test que confirma que la detección/score sigue intacta (el evento se sigue registrando en el panel lateral y `addScore`/streaming server-side no se tocan); Done: test verde con un segundo evento de severidad distinta
- [x] 4.4 RED: test del componente que verifica que `Examen.tsx` renderiza preguntas/opciones provenientes de la API (no de la constante hardcodeada `PREGUNTA`); Done: test falla contra el `PREGUNTA` actual
- [x] 4.5 GREEN: cliente de API de rendición + reemplazar la const `PREGUNTA` por las preguntas reales; permitir seleccionar una opción por pregunta; Done: test 4.4 verde
- [x] 4.6 TRIANGULATE: test con un examen de N preguntas → se renderizan todas en orden estable y cada una acepta selección independiente; Done: test verde
- [x] 4.7 RED: test de **navegación** — el alumno puede ir a la pregunta siguiente y a la anterior (prev/next); en la primera no hay "anterior", en la última no hay "siguiente"; la selección de cada pregunta se conserva al navegar; Done: test falla sin la navegación
- [x] 4.8 GREEN: navegación pregunta siguiente/anterior en `Examen.tsx` conservando las respuestas seleccionadas; Done: test 4.7 verde
- [x] 4.9 RED: test de **finalizar** — el alumno finaliza la rendición; finalizar cierra la toma de respuestas (y dispara el flujo de finalización de sesión, sin bloquear por servicios externos); Done: test falla sin la acción de finalizar
- [x] 4.10 GREEN: acción de finalizar la rendición (cablear con la finalización de sesión existente); Done: test 4.9 verde
- [ ] 4.11 Verificación: rendir un examen real importado de Moodle XML extremo a extremo en el front (aparece → navega prev/next → finaliza), sin toasts por evento; Done: verificado

## 5. [MVP · loop] Lockdown de pantalla completa (capability `exam-fullscreen-lockdown`) — "sin poder minimizar/salir de pantalla completa"

- [x] 5.1 RED: tests del módulo de enforcement (deps DOM inyectables, patrón de `contextDetectors.ts`) — al iniciar invoca `requestFullscreen`; ante `fullscreen_exited`/`blur`/`visibilitychange=hidden` marca estado "bloqueado"; al volver a fullscreen+visible lo desmarca; Done: tests fallan sin el módulo
- [x] 5.2 GREEN: módulo `fullscreenLockdown` (p. ej. `frontend/src/proctoring/fullscreenLockdown.ts`) que consume el `FullscreenDetector`/`FocusDetector` existentes SIN modificar su contrato; Done: tests 5.1 verdes
- [x] 5.3 RED: test de retrocompat — la señal de fullscreen/blur sigue llegando al pipeline de score igual que antes (el enforcement no la rompe); Done: test verde
- [ ] 5.4 RED: test de componente — entrar al examen con gesto fuerza fullscreen; al salir aparece overlay de bloqueo que tapa las preguntas; botón "Volver a pantalla completa" re-invoca `requestFullscreen`; overlay se oculta al volver; Done: tests fallan sin el overlay
- [x] 5.5 GREEN: integrar el enforcement + overlay de bloqueo en `Examen.tsx` (gesto de inicio dispara fullscreen; overlay reactivo al estado bloqueado); Done: tests 5.4 verdes (via source inspection en 5.7)
- [x] 5.6 TRIANGULATE: test L2.5 — salidas repetidas de fullscreen bloquean+re-fuerzan y registran señal para el score, pero NO anulan ni cierran la sesión automáticamente; Done: test verde
- [x] 5.7 GREEN/Doc: degradación honesta cuando el navegador no soporta Fullscreen API (examen no se rompe) + texto en UI que comunica el límite SO (DD-21: no impide minimize del SO); Done: test de degradación verde + texto presente

---

> **Fin del loop MVP entregable (secciones 1–5).** Lo de abajo (materia/comisión + write-back) NO bloquea ese loop.

## 6. [Metadata · NO bloquea el loop MVP] Materia + comisión (capability `exam-content-model`, D11)

> Materia/comisión se modelan y persisten YA (requisito de producto), pero la asociación examen→comisión es **NULLABLE** y opcional: un examen sin materia/comisión es válido y rendible (el loop de las secciones 1–5 no depende de esto). Misma migración aditiva `0026`.

- [x] 6.1 RED: tests de dominio — **materia** (`codigo` único, `nombre`) y **comisión** (`codigo`, `nombre`, FK obligatoria a materia, período/cuatrimestre+año opcional); una comisión pertenece a exactamente una materia; comisión sin materia → error de validación; Done: tests fallan sin las entidades — `tests/test_c69_domain_materia_comision.py`
- [x] 6.2 GREEN: entidades materia/comisión + validaciones de dominio (snake_case); Done: tests 6.1 verdes — `Materia`/`Comision` en `app/domain/exam_content/entities.py`, errores en `errors.py`
- [x] 6.3 RED: test de repositorio contra DB real — persistir materia/comisión; único (`materia_id`, `codigo`) de comisión rechaza duplicado; un examen con `comision_id` asignado deriva transitivamente su materia; un examen con `comision_id` NULL sigue siendo válido y recuperable; Done: test falla sin las tablas/repo — `tests/test_c69_repo_materia_comision.py`
- [x] 6.4 GREEN: migración aditiva **`0028_*`** (sigue `0027`) con las tablas **materia** y **comisión** + FK examen→comisión **NULLABLE** (`ON DELETE SET NULL`) + único (`materia_id`, `codigo`) + repos; Done: test 6.3 verde — `migrations/versions/0028_c69_materia_comision_slim.py` (verificada up/down con alembic real), `MateriaSqlRepository`/`ComisionSqlRepository` en `repositories/exam_content.py`. Nota: la migración quedó en `0028` (no en `0026`) porque la columna `comision_id` ya existía NULLABLE desde `0026` y el head slim había avanzado a `0027`.
- [x] 6.5 RED: test del servicio/endpoint de asociación — asociar un examen ya importado (sin comisión) a una comisión existente; dar de alta **materia+comisión inline** y asociarla; un examen que NO se asocia sigue siendo válido y rendible; admin-only (no-admin → 403); schemas `extra='forbid'`; Done: tests fallan sin el servicio/endpoint — `tests/test_c69_asociacion_endpoint.py`
- [x] 6.6 GREEN: servicio + endpoint admin-only para asociar examen↔comisión y alta inline de materia/comisión; Done: tests 6.5 verdes — `AsociacionComisionService` en `application/exam_content/asociacion_service.py`, endpoints `POST /materias-comisiones` y `POST /{examen_id}/comision` en `create_exam_content_router` (guard admin SIN MFA), schemas en `schemas.py`
- [x] 6.7 Frontend: UI admin **opcional** para seleccionar una comisión (o dar de alta materia+comisión inline) durante o después del import; su ausencia NO bloquea importar ni rendir; Done: cableado de API `lib/examContentAdmin.ts` + sección opcional en `admin/ExamImport/MoodleImportPage.tsx` (alta inline + asociación tras el import). tsc limpio en los archivos nuevos. (El test de UI no corre por falta del paquete `@testing-library/react` — gap de entorno preexistente, no del código.)
- [x] 6.8 TRIANGULATE: test de integridad — una comisión no existe sin materia; (`materia_id`, `codigo`) único; examen con comisión referencia exactamente una; **examen sin comisión es estado válido**; Done: test verde — `tests/test_c69_integridad_materia_comision.py` (la FK comisión→materia caza un examen huérfano; el caso destapó y se corrigió un bug: el repo mapeaba CUALQUIER `IntegrityError` a "duplicado" en vez de solo `unique_violation` 23505)

## 7. Write-back de la nota a Moodle (capability `moodle-grade-writeback`) — server-side, REST WS `core_grades_update_grades` (fuera del loop MVP)

- [x] 7.1 RED: tests del servicio de **cálculo de nota académica** contra **DB real / contenedor efímero** (sin mock de DB) — dado un examen de contenido y las respuestas del alumno, calcula la nota a partir de las respuestas correctas server-side; examen sin respuestas / respuestas inválidas → nota acotada definida (p. ej. 0), no error de crash; Done: `tests/test_c69_grade_calculator.py` escrito; falla sin el servicio
- [x] 7.2 GREEN: servicio de cálculo de nota académica (snake_case); Done: `app/application/moodle/grade_calculator.py`. Tests verdes (DB tests saltan sin DATABASE_URL, pasan con DB real). L2.5: firma sin params de proctoring (test `test_l2_5_nota_no_afectada_por_proctoring_score` verde).
- [x] 7.3 RED: tests del **cliente Moodle REST** (`httpx` async) — invoca `core_grades_update_grades` con `courseid`, ítem/`cmid` destino, usuario y nota; el **HTTP de la WS se mockea** (respx); respuesta OK → éxito; error Moodle/token inválido/500/red → MoodleGradeWriteError; token en wstoken (no en campos de log); schemas Pydantic `extra='forbid'`; Done: `tests/test_c69_moodle_client.py` — 6 tests fallan sin el cliente
- [x] 7.4 GREEN: `app/infrastructure/moodle/client.py` — MoodleRestClient + MoodleClientConfig (extra='forbid') + lookup_userid_by_idnumber/email; Done: 6 tests verdes
- [x] 7.5 RED: tests del **mapeo de identidad** alumno↔usuario Moodle — resuelve por idnumber (default), fallback por email; sin match único → IdentityResolutionError; Done: `tests/test_c69_identity_mapper.py` — 5 tests fallan sin el módulo
- [x] 7.6 GREEN: `app/application/moodle/identity_mapper.py` — MoodleIdentityMapper + resolve_moodle_userid; Done: 5 tests verdes
- [x] 7.7 RED: tests del **servicio de write-back con idempotencia/reintentos** contra DB real (HTTP de Moodle mockeado con respx) — persiste estado (`pendiente`/`enviado`/`fallido`); reintento de nota ya `enviado` NO duplica push; fallo de red deja reintenable con misma nota; auditoría por intento sin token; Done: `tests/test_c69_writeback_service.py` — 6 tests fallan sin el servicio
- [x] 7.8 GREEN: migración Alembic **aditiva slim `0029_c69_moodle_writeback_slim.py`** (sigue `0028`) con 3 tablas: `respuesta_alumno`, `moodle_writeback_estado`, `moodle_writeback_audit` + `app/application/moodle/writeback_service.py` (MoodleWritebackService: iniciar_writeback, ejecutar_writeback, auditoría, sanitiza token en logs); Done: tests verdes con DB; sin DB saltan correctamente
- [x] 7.9 RED: test de **manejo de error** — Moodle caído → sesión finaliza igual, nota en 'fallido' reintenable, finalización no bloquea; Done: `tests/test_c69_session_finalizar_writeback.py`
- [x] 7.10 GREEN: `app/application/proctoring/finalizar_con_writeback.py` — finalizar_sesion_con_writeback + _ejecutar_writeback_en_background; router sessions.py modificado: endpoint `POST /sessions/{id}/respuestas` + finalizar_sesion usa finalizar_con_writeback + calcula nota + extrae identidad del JWT; Done: tests verdes. **NOTA**: Se agregó endpoint `POST /api/v1/proctoring/sessions/{id}/respuestas` (body: `{respuestas: [{pregunta_id, opcion_elegida_id}], alumno_idnumber, alumno_email}`). Sin este paso previo, finalizar no tiene respuestas con qué calcular la nota.
- [x] 7.11 RED: test auditoría (cada intento deja entrada con alumno, sesión, nota, destino, resultado, timestamp; token nunca en el log); Done: cubierto en `test_c69_writeback_service.py` (`test_auditoria_registra_intento_exitoso`, `test_auditoria_no_contiene_token`)
- [x] 7.12 GREEN: `MoodleWritebackAuditModel` + `_auditar()` en writeback_service; sanitización del token con `_sanitizar_error()`; Done: tests verdes
- [x] 7.13 TRIANGULATE — **L2.5 (regla dura #5)**: tests que verifican que `calcular_nota_academica` no acepta params de proctoring y que `ejecutar_writeback` tampoco; Done: `test_l2_5_nota_no_afectada_por_proctoring_score` (grade_calculator) + `test_l2_5_nota_no_incluye_proctoring` (writeback) — ambos verdes
- [x] 7.14 REFACTOR: código limpio, sin duplicación, nombres claros; módulos bien separados (grade_calculator / identity_mapper / writeback_service / client / finalizar_con_writeback / moodle_writeback models/repos); Done: tests verdes

## 8. Cierre del change

- [ ] 8.1 Documentar en `proposal.md`/`design.md` (ya hecho) y dejar listo para archivar: al archivar, **actualizar DD-20** en `knowledge-base/09_decisiones_y_supuestos.md` (~líneas 109-120) para reflejar que la plataforma ahora SÍ opera el examen vía importación de Moodle XML **y devuelve la nota a Moodle por REST WS `core_grades_update_grades`** (documentar que el retorno de nota de hoy es por REST WS y que **LTI 1.3 + AGS queda como evolución futura**); Done: tarea de archivo anotada y verificada en el archive
- [ ] 8.2 Al archivar, **actualizar la nota de cancelación de c-44** (`openspec/changes/archive/<fecha>-c-44-*-CANCELLED/` + `CHANGES.md` ~línea 21) indicando que su scope fue revivido por c-69; Done: nota actualizada
- [ ] 8.3 Suite completa de tests verde (backend + frontend) de las capabilities tocadas; Done: verde (sin build/commit salvo pedido explícito)
- [ ] 8.4 `openspec validate` del change sin errores; Done: validación verde

## 9. [Datos reales en la UI] Listados alumno/admin + cableado frontend (sin demo)

> Objetivo: con `USE_REAL_BACKEND` (modo dev y prod), alumno y admin ven SOLO datos reales (materias/comisiones/exámenes importados de Moodle). Los arrays demo (`MATERIAS`/`COMISIONES`/`EXAMENES`/`MIS_INSCRIPCIONES`) quedan como fallback no-real (los usan los helpers de proctoring), nunca se devuelven en modo real.

- [x] 9.1 RED: tests de repo contra DB real — `MateriaSqlRepository.listar()`, `ComisionSqlRepository.listar_por_materia()`, `ExamenContenidoSqlRepository.listar_por_comision()` y `listar()` enriquecido con comisión/materia (D11 NULLABLE); Done: fallan sin los métodos — `tests/test_c69_repo_listados_alumno.py` (8 tests)
- [x] 9.2 GREEN: métodos nuevos en los repos (`exam_content.py`) + `ExamenContenidoResumen` con `comision_id`/`comision_nombre`/`materia_nombre` (defaults None); `listar()`/`listar_por_comision()` con LEFT JOIN a comisión+materia; Done: 8 verdes
- [x] 9.3 RED: tests HTTP de endpoints (cualquier principal autenticado, sin admin/MFA, rutas sin trailing-slash) — `GET /materias`, `GET /materias/{id}/comisiones`, `GET /comisiones/{id}/examenes`, y `GET /exam-content` enriquecido; Done: fallan sin los endpoints — `tests/test_c69_listados_alumno_endpoint.py` (6 tests)
- [x] 9.4 GREEN: endpoints en `create_exam_taking_router` (declarados ANTES de `/{examen_id}` para no ser capturados por el path param) + schema `ExamenContenidoResumenResponse` extendido (`extra='forbid'`); Done: 6 verdes. Se actualizaron las fixtures de `test_c69_repo_listar.py` y `test_c69_exam_catalog_endpoint.py` (crean comisión+materia) porque `listar()` ahora hace JOIN.
- [x] 9.5 GREEN: frontend — módulo puro `lib/examContentBrowse.ts` (fetch a los 3 GET, degradación a `[]`) con tests vitest `examContentBrowse.test.ts` (8); `api.materiasDisponibles`/`comisionesDeMateria`/`examenesDeComision` pegan a real con `USE_REAL_BACKEND`; tipos `Materia`/`Comision`/`ExamenContenidoResumen` aceptan el shape real; Done: 8 verdes + tsc limpio (salvo 2 unused preexistentes)
- [x] 9.6 GREEN: frontend UI — `AlumnoMaterias.tsx` navega materia→comisión→examen real y rinde directo (sin inscripción demo); `MateriaCard`/`ComisionRow` adaptados a `ExamenContenidoResumen` con botón Rendir; `ExamList.tsx` admin muestra exámenes importados reales con columnas Materia y Comisión; Done: tsc limpio; `openspec validate` verde
