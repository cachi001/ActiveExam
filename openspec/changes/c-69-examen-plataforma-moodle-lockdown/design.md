## Context

El flujo de examen del alumno es hoy una maqueta funcional de proctoring: el motor de visión, los detectores de contexto, el streaming de eventos y el score son REALES (`useExamProctoring.ts`), pero **el examen en sí es de mentira**: una sola pregunta hardcodeada (`Examen.tsx`, const `PREGUNTA`, ~líneas 25-34) y ningún modelo de contenido en la DB. El CRUD `backend/app/presentation/api/v1/exams/` modela la **configuración de proctoring** del examen (umbral, detectores, ventana, retención, biometría), no su contenido (preguntas/respuestas).

Durante la rendición, un `useEffect` (`Examen.tsx` ~107-122) dispara un toast al alumno por CADA evento de proctoring (`Rostro ausente · Alta · +X pts`). Esto le filtra al examinado la lógica de detección y cuánto suma cada señal.

Existe DETECCIÓN de salida de fullscreen / blur / pestaña (`contextDetectors.ts`: `FullscreenDetector`, `FocusDetector`) cableada al pipeline (`useExamProctoring.ts`), pero sólo registra evento + suma score; **no bloquea ni re-fuerza** la pantalla completa.

**Cambio de postura del proyecto (CRÍTICO).** Hasta hoy DD-20 (`09_decisiones_y_supuestos.md:109-120`) y la visión fijaban: *el LMS opera el examen; el proctoring se integra alrededor y NO crea ni importa exámenes*. c-44 fue cancelado por exactamente esto (`CHANGES.md:21`). El dueño decidió el 2026-06-26 **anular esa postura**: la plataforma ahora SÍ opera el examen, con preguntas en la DB alimentadas por importación de Moodle XML. Este change materializa esa anulación. La integración profunda con Moodle (REST API, LTI 1.3, AGS, NRPS, plugin `quizaccess`) sigue siendo un change futuro aparte y NO entra acá.

**Constraints de stack (reglas duras).** Postgres slim (sin TimescaleDB hoy); Alembic aditivo en rama slim (patrón de `0023`, próxima revisión = `0026`). Python snake_case; Pydantic `extra='forbid'`; tests sin mocks de DB (DB real / contenedor efímero); React PascalCase; TDD estricto. L2.5: el examen NUNCA sanciona; el lockdown bloquea/re-fuerza, no expulsa. Cliente = sensor no confiable: corrección y opción correcta viven server-side.

## Goals / Non-Goals

**Goals:**
- Modelar examen de contenido + preguntas + opciones + opción correcta en Postgres (slim, Alembic aditivo) y exponer una API de lectura para rendir que NUNCA filtra la opción correcta al alumno.
- Importar Moodle XML (al menos `multichoice` y `truefalse`) a ese modelo, admin-only, con reporte de importadas/omitidas.
- **Devolver la nota académica a Moodle**: al finalizar la sesión de examen, calcular la nota server-side y escribirla en Moodle vía REST WS `core_grades_update_grades`, con mapeo de identidad alumno↔Moodle, idempotencia/reintentos, estado persistido, manejo de error y auditoría. Escribir SÓLO nota académica (nunca el score de proctoring).
- Reemplazar la pregunta hardcodeada de `Examen.tsx` por las preguntas reales de la API.
- Eliminar el toast por evento de proctoring durante el examen (sin tocar detección/score server-side).
- Forzar pantalla completa al iniciar el examen y reaccionar (overlay de bloqueo + re-forzado) ante salida de fullscreen / blur / pestaña oculta, hasta que el alumno vuelva.
- Documentar honestamente el límite: el navegador no impide el minimize del SO ni ve fuera del sandbox (DD-21).

**Non-Goals:**
- REST API de Moodle para traer CONTENIDO (listar cursos/quizzes, leer banco de preguntas): **fuera de alcance** — las Web Services del core de Moodle no exponen el contenido de las preguntas; por eso el contenido entra por XML. (El write-back de la NOTA por REST WS `core_grades_update_grades` SÍ está en alcance — ver Goals y D7.)
- LTI 1.3 / AGS / NRPS (roster) / plugin Moodle `quizaccess`: change futuro `integracion-lms-lti` (DD-20 forma futura). El retorno de nota de hoy es por REST WS, NO por AGS.
- Tipos de pregunta complejos de Moodle (cloze, drag&drop, calculated, essay con autograding): fuera de alcance; se omiten con reporte.
- Feedback por pregunta sofisticado / rúbricas avanzadas: fuera de alcance. La corrección produce una nota académica simple (respuestas correctas) suficiente para el write-back.
- Lockdown nativo a nivel SO (L5): explícitamente imposible desde una web app (DD-21).

## Decisions

### D1 — Moodle XML, no la REST API de Moodle
**Decisión**: el importador parsea el export "Moodle XML" subido por el admin.
**Por qué**: las Web Services del core de Moodle **no exponen el contenido** (enunciado/opciones/respuesta) de las preguntas; el formato Moodle XML sí. Una integración por REST API no podría traer el banco de preguntas.
**Alternativas**: (A) REST API de Moodle → descartada (no expone contenido); (B) GIFT format → más pobre que XML, menos universal; (C) carga manual pregunta por pregunta → no escala al banco real. **Adoptada: Moodle XML.**

### D2 — Modelo de contenido SEPARADO de la configuración de proctoring existente
**Decisión**: nuevas tablas de contenido (examen de contenido / pregunta / opción) en una migración aditiva, sin tocar el modelo de configuración de proctoring (`exam_config`) ni `proctoring_session`.
**Por qué**: separación de responsabilidades — "qué se pregunta" vs "cómo se supervisa". Mantiene aditividad (patrón `0023`) y no rompe el CRUD de configuración existente. La vinculación entre el examen de contenido y el examen-config/sesión se resuelve por id (FK opcional o referencia), a decidir en apply según cómo se selecciona el examen activo en el front (`examenActivo` del store).
**Alternativas**: (A) extender `exam_config` con preguntas → mezcla responsabilidades, migración no aditiva; (B) tabla nueva separada → **adoptada**.

### D3 — La opción correcta NUNCA viaja al cliente
**Decisión**: la API de rendición (`exam-taking-api`) devuelve preguntas y opciones SIN el flag de opción correcta. La marca de correcta se persiste server-side y sólo se usa para corrección server-side.
**Por qué**: regla dura #6 (cliente = sensor no confiable) + integridad del examen. Un alumno que inspecciona la respuesta de red no debe poder leer la respuesta correcta.
**Alternativas**: (A) mandar todo y ocultar en UI → trivialmente bypasseable, descartada; (B) proyección server-side sin el campo correcto → **adoptada**.

### D4 — Enforcement de fullscreen como capa NUEVA sobre los detectores existentes
**Decisión**: el lockdown vive en un módulo nuevo (p. ej. `frontend/src/proctoring/fullscreenLockdown.ts`) + estado/overlay en `Examen.tsx`. Reusa el `FullscreenDetector`/`FocusDetector` existentes SIN modificar su contrato (siguen emitiendo la misma señal hacia el score). El enforcement: (a) `requestFullscreen()` al iniciar el examen (requiere gesto del usuario → se dispara en el click de "Comenzar/Iniciar"); (b) al recibir `fullscreen_exited` / `blur` / `visibilitychange=hidden` → montar un overlay bloqueante que tapa el examen y ofrecer "Volver a pantalla completa" que re-invoca `requestFullscreen()`; (c) ocultar el overlay cuando se vuelve a fullscreen y la pestaña está visible.
**Por qué**: no romper la detección/score existente (retrocompat) y mantener el límite L2.5 (bloquea, no expulsa ni anula). El re-forzado automático puro no siempre es posible sin gesto del usuario en algunos navegadores → por eso el overlay ofrece el botón explícito además del intento automático.
**Alternativas**: (A) modificar `browser-context-detectors` para que el detector bloquee → acopla detección con enforcement y arriesga el spec vigente, descartada; (B) capa nueva que consume señales → **adoptada**.

### D5 — Quitar SÓLO el toast por evento, no el resto del feedback
**Decisión**: eliminar el `useEffect` de toasts por evento (`Examen.tsx` ~107-122) y su `SEV_TOAST`. El panel lateral "Señales de integridad (en vivo)" y el modal de monitor adicional / alerta crítica son comportamientos separados; este change toca ÚNICAMENTE el toast por evento. (Si el dueño quiere además ocultar el panel lateral, es decisión aparte y se nota como open question.)
**Por qué**: el pedido es no filtrar al alumno los eventos uno por uno; la detección, el score y la persistencia server-side se mantienen intactos.

### D6 — Límite honesto del anti-minimizar (DD-21)
**Decisión**: documentar en spec y en la UI que el navegador NO puede impedir el minimize del SO ni ver fuera del sandbox; se DETECTA (blur / visibilitychange) y se REACCIONA (overlay + re-forzado), no se PREVIENE a nivel SO.
**Por qué**: coherencia con DD-01 (L5 es otro proyecto) y DD-21 (web app, no lockdown nativo). Evita vender una garantía falsa.

### D7 — Write-back de la nota por REST WS `core_grades_update_grades`, NO por LTI/AGS
**Decisión**: la nota vuelve a Moodle vía la REST Web Service `core_grades_update_grades`, invocada por un **cliente Moodle REST server-side** (`httpx` async). El admin configura: base URL de Moodle, **token** de Web Services (guardado como secreto en Vault/secret manager, inyectado server-side, NUNCA en el cliente ni en el repo), `courseid` y el ítem de calificación / `cmid` destino.
**Por qué**: el dueño confirmó REST WS como vía de hoy. `core_grades_update_grades` permite empujar la nota de un ítem por usuario sin requerir el ciclo de lanzamiento LTI. Es el menor cambio para cerrar el ciclo "rendir → nota en Moodle".
**Alternativas**: (A) LTI 1.3 + AGS (Assignment and Grade Services) → más estándar y bidireccional, pero requiere registro de la tool, JWT/keyset, line items y un lanzamiento LTI; **mayor superficie**, se difiere a `integracion-lms-lti` (evolución futura). (B) Edición manual de la nota en Moodle → no escala, descartada. **Adoptada: REST WS `core_grades_update_grades`; LTI 1.3/AGS como evolución futura.**

### D8 — Disparo server-side al finalizar la sesión (cliente = sensor no confiable)
**Decisión**: el cálculo de la nota académica y el envío a Moodle se originan en el **backend**, al finalizar la sesión de examen. El cliente NUNCA invoca la WS de Moodle ni transporta el token.
**Por qué**: regla dura #6 — el cliente es un sensor no confiable; una nota disparada desde el navegador sería falsificable. El backend es la única fuente de verdad de la corrección.
**Alternativas**: (A) disparo desde el front al terminar → falsificable, expone el token, descartada; (B) disparo server-side al finalizar (hook de finalización de sesión / job encolado) → **adoptada**.

### D9 — Mapeo de identidad alumno↔Moodle: `idnumber` default, email fallback
**Decisión**: el usuario Moodle destino se resuelve por el `idnumber` de Moodle como criterio por defecto, con **fallback por email**. Si no se resuelve un usuario único, NO se envía a un usuario arbitrario: el envío se marca fallido para revisión.
**Por qué**: el `idnumber` (legajo/padrón institucional) es el identificador estable y menos ambiguo; el email cubre los casos en que el `idnumber` no está cargado. Evitar enviar la nota al usuario equivocado es prioritario sobre enviarla siempre.
**Alternativas**: (A) sólo por email → frágil ante cambios/alias de correo; (B) sólo por `idnumber` → falla si no está cargado; (C) `idnumber` con fallback email → **adoptada**.

### D10 — Idempotencia, reintentos, estado persistido y auditoría; lo que se escribe es la nota ACADÉMICA
**Decisión**: cada envío de nota persiste su **estado** (p. ej. `pendiente` / `enviado` / `fallido`) ligado a la sesión/examen+usuario; el envío es **idempotente** (un reintento de una nota ya `enviado` no duplica el push a Moodle) y **reintenable** ante fallo de red / error transitorio de Moodle, sin recalcular una nota distinta. Si Moodle no responde, la finalización del examen del alumno NO se bloquea: la nota queda persistida y el envío reintenable. Cada intento (éxito/fallo) deja entrada en el **audit log** (alumno, sesión, nota, destino `courseid`/ítem, resultado, timestamp) — **el token nunca se loguea**. **L2.5 (regla dura #5)**: lo que se escribe en Moodle es la **nota académica** (respuestas correctas); el **score/flags de proctoring NO se escriben** como calificación ni se convierten en penalización automática. Nota académica y score/proctoring se mantienen **separados**; el proctoring nunca es veredicto automático.
**Por qué**: la red a Moodle puede fallar; perder o duplicar notas es inaceptable. La auditoría es requisito de cadena de custodia. La separación nota↔proctoring es contrato L2.5.
**Alternativas**: (A) fire-and-forget sin estado → pierde notas ante fallo, descartada; (B) estado persistido + reintento idempotente + auditoría → **adoptada**.

### D11 — Materia + comisión: obligatorias-de-producto, pero NULLABLE en el MVP
**Decisión** (dueño, 2026-06-27): se modelan y persisten **materia** (`codigo` único, `nombre`) y **comisión** (`codigo`, `nombre`, FK obligatoria a materia, período/cuatrimestre+año opcional, único (`materia_id`, `codigo`)) como concepto **real del producto** — quedan en los specs y en el modelo, NO se difieren a otro change. PERO la asociación **examen→comisión es OPCIONAL en esta etapa**: la FK `comision_id` del examen de contenido es **NULLABLE**. Un examen SIN comisión (y por ende sin materia) es un **estado válido** del MVP: se puede importar, persistir y rendir sin ellas. El admin puede asociar una comisión existente o **dar de alta materia+comisión inline** después, sin reimportar. Integridad: una comisión pertenece a **exactamente una** materia; si un examen tiene comisión, es exactamente una y de ella deriva transitivamente la materia.
**Por qué**: el dueño lo dejó textual — *"es obligatorio, pero por ahora si no tienen comisión ni materia no hay problema, tenemos que tenerlo hecho ya"*. Se necesita el concepto modelado y persistido YA (no se difiere), pero el loop entregable del MVP (importar → persistir → rendir → navegar → finalizar → lockdown) NO debe bloquearse por falta de materia/comisión, que el XML de Moodle ni siquiera trae. NULLABLE concilia "modelado y obligatorio como concepto" con "no bloquea el MVP".
**Alternativas**: (A) FK examen→comisión NOT NULL desde el día uno → bloquearía importar/rendir sin comisión, contradice al dueño, descartada; (B) diferir materia/comisión a un change futuro → contradice "tenemos que tenerlo hecho ya", descartada; (C) modelar materia/comisión ahora con FK **NULLABLE** + alta/asociación opcional por el admin → **adoptada**.
**Implicancia de tareas**: las tareas de materia/comisión van en un **bloque separado, explícitamente NO bloqueante** del loop MVP (ver `tasks.md`); el examen de contenido del loop se crea con `comision_id` NULL.

## Risks / Trade-offs

- **[Anula DD-20 y revive c-44]** → Al archivar este change hay que **actualizar la KB**: editar DD-20 (`knowledge-base/09_decisiones_y_supuestos.md:109-120`) para reflejar que la plataforma ahora SÍ opera el examen vía importación de Moodle XML **y devuelve la nota a Moodle por REST WS `core_grades_update_grades`** (documentar que el retorno de nota de hoy es por **REST WS** y que **LTI 1.3 + AGS queda como evolución futura** en `integracion-lms-lti`), y actualizar la **nota de cancelación de c-44** (`openspec/changes/archive/<fecha>-c-44-*-CANCELLED/` + `CHANGES.md` ~línea 21) indicando que su scope fue revivido por c-69. Anotado como tarea de cierre en tasks.md.
- **[Moodle no disponible / token inválido al finalizar]** → El push a `core_grades_update_grades` puede fallar por red, Moodle caído o token inválido. Mitigación: estado de envío persistido + reintento idempotente; la finalización del examen NO se bloquea por Moodle; cada intento queda auditado (sin loguear el token). El token vive en el secret manager (Vault), nunca en cliente ni repo.
- **[Mapeo de identidad ambiguo]** → Un alumno sin `idnumber` ni email mapeable, o con múltiples coincidencias, podría enviar la nota al usuario equivocado. Mitigación (D9): `idnumber` default + email fallback; si no hay match único, NO se envía a un usuario arbitrario y el envío se marca fallido para revisión.
- **[Contaminar la nota con el score de proctoring]** → Riesgo de que el score/flags se cuelen en la calificación enviada (violaría L2.5). Mitigación: separación explícita nota académica ↔ score; test que verifica que la nota enviada deriva sólo de respuestas correctas, sin penalización automática de proctoring.
- **[Fullscreen API depende del navegador / gesto del usuario]** → El re-forzado automático puede requerir un gesto; mitigación: overlay con botón explícito "Volver a pantalla completa" además del intento automático. Degradación honesta si el navegador no soporta Fullscreen API: se documenta el límite, el examen no se rompe.
- **[Moodle XML tiene muchos tipos de pregunta]** → Alcance acotado a `multichoice` y `truefalse`; los tipos no soportados se OMITEN con reporte (no se rompe el import). Mitigación: el reporte lista preguntas omitidas y su tipo.
- **[Re-import duplicaría preguntas]** → Definir estrategia idempotente/controlada (reemplazo del examen de contenido o detección de duplicados) — ver Open Questions; mitigación mínima: import crea un examen de contenido nuevo y el admin elige cuál usar.
- **[Opción correcta filtrada por error]** → Test server-side que verifica que la proyección de rendición NO incluye el campo de opción correcta (regla dura #6).
- **[Romper la detección/score al meter enforcement]** → El enforcement es capa nueva que NO modifica el contrato del detector; test de retrocompat de la señal de fullscreen hacia el score.

## Migration Plan

1. **Backend, aditivo**: nueva migración Alembic rama slim `0026_*` (sigue `0025`), patrón aditivo de `0023` (tablas nuevas, FK con `ON DELETE CASCADE`, índices). Crea: examen de contenido / pregunta / opción **más materia y comisión** (D11), con la FK examen→comisión **NULLABLE** y el único (`materia_id`, `codigo`). `alembic downgrade` dropea sólo las tablas nuevas — no destructivo para el resto.
2. **Dominio + repos + servicio de import + endpoints** (TDD, DB real/contenedor efímero).
3. **Write-back (backend, aditivo)**: tabla/estado de envío de nota en la misma migración aditiva `0026_*`; cliente Moodle REST (`httpx` async) sobre `core_grades_update_grades`; servicio de cálculo de nota académica; servicio de write-back idempotente con reintentos; hook de disparo al finalizar la sesión; entradas de audit log. Config (base URL, `courseid`, ítem/`cmid`) y **token** (vía secret manager) inyectados server-side. Tests: DB real/efímera para el estado; el HTTP de la WS se mockea (fake server / respuestas HTTP), NUNCA la DB.
4. **Frontend**: cablear `Examen.tsx` a la API de rendición; quitar toasts; módulo de fullscreen lockdown + overlay. (El write-back NO tiene disparo desde el cliente.)
5. **Rollback**: `alembic downgrade slim@0025` (dropea también la tabla de envío de nota) + revertir los cambios de front. Aditivo → seguro.
6. **Al archivar**: actualizar DD-20 (incluyendo que el retorno de nota es por REST WS y LTI/AGS es evolución futura) y la nota de c-44 (ver Risks).

## Open Questions

- ¿Cómo se vincula el examen de contenido con el `examenActivo` del store / la sesión de proctoring? (FK explícita examen-config ↔ examen-contenido, o referencia por id elegida por el admin). A resolver en apply mirando `frontend/src/lib/store` y el flujo de selección de examen.
- Estrategia de re-import: ¿reemplazo total del examen de contenido, versionado, o detección de duplicados por idmoodle? (Default mínimo: cada import crea un examen de contenido nuevo.)
- ¿Se oculta también el panel lateral "Señales de integridad (en vivo)" al alumno, o sólo el toast? (Este change quita sólo el toast; el panel queda como decisión separada del dueño.)
- Alcance de la "nota": este change corrige las respuestas server-side, persiste la nota académica y la **escribe en Moodle** (write-back). El detalle de la fórmula de calificación (escala, redondeo, ítem destino exacto) se resuelve en apply contra la config del admin y el ítem Moodle.
- ¿De dónde sale el `courseid` y el ítem/`cmid` destino por examen? (¿config global del Moodle, o por examen de contenido?) A resolver en apply; default mínimo: configuración por examen provista por el admin.
- ¿El `idnumber`/email del alumno ya está disponible en nuestro modelo de usuario, o hay que mapearlo desde Keycloak/directorio? A resolver en apply mirando el modelo de identidad existente.
- **Materia/comisión (D11)**: en el MVP la asociación examen→comisión es NULLABLE y opcional. Queda abierto: (a) ¿en qué momento post-MVP pasa a ser obligatoria al egreso/publicación del examen, y bajo qué change?; (b) ¿de dónde sale el `codigo` de materia/comisión — alta manual del admin (default asumido), o se mapea desde el `courseid`/curso de Moodle?; (c) ¿la comisión define quién puede rendir (roster/habilitación), o eso queda para el flujo de habilitación existente? Default mínimo del MVP: alta/asociación manual por el admin, sin gate de obligatoriedad.
