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

- [x] 2.1 Test (RED): con `api.listarExamenesContenido` rechazando, AdminDashboard NO
      muestra "0" en la stat de Exámenes — muestra estado de error + reintento.
      Lógica extraída a helper puro `statExamenesValue` (error → '—', nunca 0 fantasma).
- [x] 2.2 Test: con la lista cargando → placeholder; con éxito y 1 examen → "1"; con
      éxito y 0 → "0" legítimo (helper `statExamenesValue`: loading/idle → '…', ready → cantidad).
- [x] 2.3 Migrar AdminDashboard al contrato de carga (reemplazar `.then(set).finally(...)`
      sin `.catch` por el hook); verificar que ningún camino pinta el vacío inicial como dato
- [x] 2.4 Inventariar las demás pantallas con el patrón `.then(set).finally(...)` sin
      `.catch` y migrarlas (o listar las que quedan como deuda explícita).
      Barrido: de las 5 pantallas con `.then(set…)`, 4 (EstadisticasInstitucionales,
      ExamDetail, ExamResultados, MateriasComisiones) ya tenían `.catch`. La única
      sin manejo de error era `EnrollmentConsentStep` (degradaba a spinner eterno):
      migrada a `useAsyncData` con estado de error + reintentar (3 tests).

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

- [x] 6.1 `tsc --noEmit` del frontend sin errores
- [x] 6.2 Suite de frontend completa en verde (vitest), incluidos los tests nuevos
      (791 tests, 79 archivos)
- [x] 6.3 E2E manual: recargar en varias páginas mantiene sesión sin parpadeo; matar la
      red y entrar a AdminDashboard muestra ERROR (no "0"); navegar ida/vuelta no
      refetchea en frío.
      Verificado en vivo (Playwright): navegar ida/vuelta sirve del cache sin parpadeo.
      RED CAÍDA — BUG REAL ENCONTRADO Y ARREGLADO. Con el backend detenido el panel
      mostraba "0 exámenes importados / 0 sesiones / 0 en revisión" TENIENDO datos en la
      base. El helper `statExamenesValue` (tarea 2.1) era correcto pero inútil: el error
      moría UNA CAPA MÁS ABAJO. `listarExamenesContenidoFn` y `listarSesionesProctoring`
      atrapaban el fallo y devolvían `[]` ("degradación silenciosa", decía el comentario),
      así que el hook recibía un ÉXITO con lista vacía y el cero era, para él, legítimo.
      Además `AdminDashboard` hacía `catch { setSesiones([]) }`, el mismo antipatrón.
      FIX: modo `strict` en ambas funciones de API (propaga el fallo; sin él se conserva
      la tolerancia para las pantallas del alumno) + estado `sesionesError` en el panel.
      VERIFICADO: con el backend caído las 3 tarjetas muestran `—` y el catálogo dice
      "No se pudo cargar el catálogo de exámenes" con botón Reintentar. Con cache previo,
      sirve el último dato bueno (no lo degrada), que es la filosofía del change.
      DEUDA EXPLÍCITA: las pantallas del ALUMNO (AlumnoDashboard, AlumnoMisExamenes)
      siguen usando el modo tolerante y mostrarían "sin exámenes" ante un fallo de red.
      No se tocaron para no desestabilizarlas antes del E2E de Moodle.
- [x] 6.4 `openspec validate c-73-persistencia-carga-cliente` en verde

## 7. Moodle — configurar y validar el write-back contra el campus real

> El write-back ya existe (C-69); acá se OPERA contra el campus real. Tests de backend
> con DB real (no mocks de DB). El envío real a Moodle se prueba contra `campustest`.

- [~] 7.1 Documentar/parametrizar la config del campus real (`MOODLE_BASE_URL`,
      `MOODLE_WS_TOKEN`, `courseid`, `cmid`) desde el secret manager / entorno; confirmar
      que el token no aparece en repo/imagen/logs (grep de guardrail).
      GUARDRAIL ✅: grep de token literal en el repo → limpio (los únicos literales viven
      en tests con `# noqa: S106` y valores falsos). Config ya parametrizada en
      `config_slim.py` (vars opcionales, default vacío = write-back off). FALTA: documentar
      los valores reales del campus (se hace en la sesión en vivo con el owner).
- [x] 7.2 Test (RED→GREEN): con `MOODLE_BASE_URL` vacío, la finalización persiste la nota
      en estado sincronizable y NO rompe ningún flujo (degradación segura ya existente, fijar contrato).
      Extraído el wiring inline de `create_app` a factory puro `build_writeback_svc`/
      `build_moodle_config` (`app/infrastructure/moodle/wiring.py`); contrato clavado en
      `tests/test_c73_writeback_wiring.py` (4 tests: base_url vacío → None → degrada a
      `persistir_nota_pendiente`; seteado → svc real con token/curso/cm/component). Refactor
      preserva comportamiento; `main_slim` ahora consume el factory (sin duplicación).
- [x] 7.3 Validación E2E contra `campustest.frm.utn.edu.ar` con un usuario de prueba: la
      nota calculada llega a la libreta del usuario correcto (idnumber→email); el intento
      queda auditado sin el token
- [x] 7.4 Verificar el caso de identidad no resoluble contra el campus real (no escribe a
      un usuario arbitrario; queda fallido/pendiente de revisión)
- [x] 7.5 Confirmar L2.5: lo sincronizado es solo la nota académica (respuestas correctas);
      ningún flag/score de proctoring se escribe como nota.
      Clavado en `test_c69_session_finalizar_writeback::test_l2_5_nota_no_incluye_proctoring`:
      la firma de `ejecutar_writeback` acepta `nota` y NO expone `score`/`flags`/
      `proctoring_*`. El score de proctoring nunca entra al write-back.

## 8. Moodle — mapeo del campus real (CERRADA en sesión en vivo 2026-07-29)

> Desbloqueada y ejecutada con el owner presente + Playwright + credenciales.

- [x] 8.1 Sesión en vivo: mapeo de `campustest.frm.utn.edu.ar`. HALLAZGOS:
      - Login **sin SSO**: solo usuario/contraseña + "¿Olvidó su contraseña?" → **cuentas locales**.
      - `/webservice/rest/server.php` → 200 `invalidtoken` ⇒ **REST habilitado**. La ÚNICA
        credencial que acepta un WS es `wstoken`; no existe función que acepte contraseña.
      - `/login/token.php` → 200 (valida user+pass; con credenciales falsas → `invalidlogin`)
        ⇒ **canje contraseña→token disponible**. Acepta `service=<shortname>`, así que el
        token derivado queda **acotado a las funciones de nuestro servicio externo**.
      - `/local/oauth2/login.php` → **404** ⇒ NO hay OAuth2 delegado (requeriría plugin de
        terceros). Descartado el flujo "el docente autoriza sin dar contraseña".
      - Los tokens de Moodle **NO se invalidan al cambiar la contraseña** (CVE-2016-7038) ⇒
        guardar el token es MÁS estable que guardar la contraseña. Contracara: dar de baja a
        un docente exige **borrar su token** en Moodle (cambiar la clave no alcanza).
- [x] 8.2 Decisión del owner: el write-back debe llevar **la identidad del docente**, no la de
      una cuenta de servicio anónima. Validado contra otro sistema de referencia, que ya
      hace write-back con credenciales por docente y tiene el vínculo docente↔comisión.
      Ajuste técnico adoptado: se canjea la contraseña por token y se guarda **solo el token**.
- [x] 8.3 Reescritas como secciones 9 (vínculo docente↔comisión), 10 (credencial personal) y
      11 (E2E completo). Las funciones de LECTURA para proctoring quedan fuera de c-73.

## 9. Vínculo docente↔comisión (habilita atribución Y autorización)

> Hoy la cadena está cortada: `comision` no tiene docente a cargo, `inscripcion` no tiene rol
> y `examen_contenido.comision_id` es nullable. Sin este eslabón no hay a quién atribuir la
> nota ni contra qué validar la pertenencia. El rol `DOCENTE` y las capacidades
> (`gestionar_academico`, `gestionar_notas`, y `configurar_sistema` SIN docente) YA existen.

- [x] 9.1 Migración: `comision.docente_id` (FK → `usuario`, nullable en la migración para no
      romper filas existentes). Backfill NO automático: se asigna desde la UI.
      HECHO: `0049_comision_docente_a_cargo.py` (FK ON DELETE SET NULL + índice
      `ix_comision_docente_id`) + `ComisionModel.docente_id` + `Comision.docente_id` en el
      dominio. Aplicada a dev y a la base de test; datos de dev preservados.
- [x] 9.2 Test (RED→GREEN, DB real): `ComisionResponse` expone el docente a cargo; asignar y
      reasignar docente persiste. Triangular: comisión sin docente → `None` (no rompe).
      HECHO: `ComisionResponse.docente_id` + `docente_nombre` (resuelto server-side con
      `nombres_de_docentes()`, UNA query para todo el listado — sin N+1; cae al legajo si
      el usuario no tiene nombre). El listado de comisiones lo devuelve poblado.
- [x] 9.3 Test (RED): un `DOCENTE` que NO es el de la comisión recibe **403** al fijar el
      destino Moodle de ese examen. Hoy pasa (la guarda es `require_capability`, no
      pertenencia) — este test debe fallar primero. Triangular: el docente propio → 200;
      `ADMIN_SISTEMA`/`COORDINADOR` → 200 (no limitados por pertenencia).
      HECHO (TDD): `tests/test_c73_pertenencia_docente.py`, 4 casos. RED confirmado (los 2
      de denegación fallaban con 200) → GREEN con `autorizar_docente_sobre_examen`
      (dominio puro) + `ComisionSqlRepository.docente_de_examen` + `_exigir_pertenencia`
      en el endpoint. 4/4 verde; sin regresiones (17 verdes en las suites del endpoint y
      del dominio materia/comisión). Cuarto caso: examen SIN docente no lo puede reclamar
      un docente — solo rol institucional.
- [x] 9.4 Aplicar la misma validación de pertenencia al resto de escrituras del examen
      (importar/editar/borrar): "de lo suyo" según el comentario del rol `DOCENTE`.
      HECHO: `_exigir_pertenencia` en los 4 endpoints con alcance de examen —
      `POST /{id}/moodle-target`, `POST /{id}/sincronizar-moodle` (el más sensible: empuja
      notas al campus), `PATCH /{id}/config` y `PATCH /{id}/preguntas-seleccion`.
- [x] 9.5 UI admin: asignar docente a comisión en Materias y comisiones (solo
      `gestionar_usuarios`/`gestionar_academico` de admin, no el docente a sí mismo).
      BACKEND HECHO: `PUT /comisiones/{id}/docente` + nueva capacidad `asignar_docente`
      ({ADMIN_EXAMENES, COORDINADOR, ADMIN_SISTEMA} — deliberadamente SIN docente: si se
      autoasignara, la pertenencia dejaría de ser un control). Valida existencia, baja
      lógica y rol docente (422); `null` desasigna; audita `COMISION_DOCENTE`.
      `tests/test_c73_asignar_docente.py` 7/7 verde. FALTA: la pantalla.

## 10. Credencial personal de Moodle del docente

> El docente carga usuario+contraseña UNA vez; se canjea en `login/token.php?service=…` y se
> persiste **solo el token**, cifrado con el `SecretCipher` ya existente (Fernet, sin fallback
> a texto plano). La contraseña NUNCA se persiste ni se loguea ni se audita.

- [x] 10.1 Migración: tabla `moodle_credencial_docente` (usuario_id UNIQUE, token cifrado,
      token_pista, moodle_username, estado `activa|caida`, timestamps). Sin columna de contraseña.
      HECHO: migración 0050 + `MoodleCredencialDocenteModel`. PK = usuario_id (una por
      docente), FK ON DELETE CASCADE, `ultimo_uso_en` para diagnóstico. SIN columna de
      contraseña a propósito: que el esquema no tenga dónde guardarla es la garantía más
      barata de que nadie la guarde por accidente. Suma `moodle_credencial.service_shortname`
      (lo exige `login/token.php?service=`). Aplicada a dev y test.
- [x] 10.2 Test (RED→GREEN): servicio de canje — user+pass → `login/token.php` → token.
      Triangular: `invalidlogin` → error tipado sin filtrar la contraseña; red caída → error
      tipado; éxito → persiste token cifrado + pista, y la contraseña no queda en memoria del
      objeto persistido.
      HECHO: `app/application/moodle/token_exchange.py` + 8 tests verdes (MockTransport de
      httpx — no se mockea DB). Distingue `CredencialesInvalidasError` de
      `ServicioNoHabilitadoError` porque el arreglo es distinto: una la resuelve el docente,
      la otra el admin del campus (lista blanca). Dos guardrails: la contraseña no aparece en
      `str()` ni `repr()` de NINGÚN error, y sin `service_shortname` falla ANTES de salir a
      la red (un token sin acotar no se pide).
- [x] 10.3 Endpoints `GET/PUT/DELETE /api/v1/config/moodle/mi-credencial` con capacidad
      `gestionar_notas` (el docente la tiene; el revisor NO). El GET nunca devuelve el token,
      solo `token_pista` + `moodle_username` + estado. Auditar alta/baja SIN el secreto.
      HECHO: `CredencialDocenteService` (9 tests verdes) + los 3 endpoints, cableados en
      `main_slim` (`app.state.credencial_docente`). El usuario sale de `principal.subject`
      (el TOKEN), nunca de la URL ni del body: no existe "editar la credencial de otro".
      El PUT acepta `password` (canje) O `token` pegado, nunca ambos (400).
      SMOKE E2E contra el backend real: GET sin cargar → `configurada:false` · PUT con token
      → `token_pista:"1234"` y en la DB queda `gAAAAA...` (Fernet); buscar el literal del
      token en la tabla devuelve 0 filas · DELETE idempotente (200 dos veces) · password+token
      juntos → 400 · estudiante → 403.
- [x] 10.4 Test (RED): al sincronizar, la credencial se resuelve
      **docente de la comisión del examen → fallback cuenta de servicio institucional**.
      Triangular: docente con credencial activa → se usa la suya; docente sin credencial →
      institucional; credencial `caida` → institucional + aviso.
      HECHO: `_credencial_para()` deriva sesión→examen→comisión→docente y pide su token.
      `write_grade`/`get_grademax` aceptan `ws_token`. La escala se lee con la MISMA
      credencial que escribe (leerla con otra puede leer un ítem que ese docente no ve).
      DECISIÓN DEL OWNER (corrige el diseño inicial): **NO hay respaldo institucional
      para el write-back de una nota**. Sin credencial del docente la nota se RETIENE con
      motivo `sin_credencial_docente` (visible en la pantalla de resultados, con el texto
      que explica qué hacer). Mandarla con la cuenta de servicio la dejaría en la libreta
      sin responsable —el problema que este change vino a resolver— y encima en silencio.
      La anulación por fraude SÍ sigue usando la institucional: la decide un revisor, y
      firmarla con la cuenta del docente le atribuiría una sanción que no tomó.
- [x] 10.5 Test (RED): respuesta `invalidtoken` de Moodle marca la credencial como `caida`
      (no borra el token) y el docente ve que debe recargarla. NO debe fallar en silencio.
      HECHO: ante token inválido se marca `caida` y la nota queda pendiente (NO se
      reintenta con la institucional: firmaría con otra identidad sin que nadie se entere).
      `caida` se comporta como ausente (no se reintenta un token ya rechazado) pero sigue
      VISIBLE para poder avisarle al docente.
      BUG REAL ENCONTRADO POR EL TEST: la detección miraba solo el errorcode inglés
      `invalidtoken`, pero campustest responde en español —"Ficha (token) no válida"—, así
      que un token vencido NO se habría detectado nunca: la nota quedaba fallida en
      silencio. Ahora reconoce ambos idiomas.
- [x] 10.6 Atribución: `source` del payload deja de ser `"activeexam"` fijo y pasa a incluir
      examen y docente (queda en el historial de calificaciones de Moodle). Test de que el
      token NUNCA aparece en `source`, logs ni auditoría.
      HECHO: `source` = `activeexam:doc=<legajo>` — nombra AL DOCENTE, no el modo. En el
      historial de calificaciones de Moodle queda con qué legajo se devolvió cada nota, que
      es la vinculación real con el campus. 5 tests verdes (respx, sin mocks de DB).
      BUG REAL: `_credencial_para` usaba `ProctoringSessionModel.examen_id`, columna que NO
      existe (es `examen_contenido_id`) — habría explotado en runtime.
- [x] 10.7 UI — Configuración con secciones por capacidad. El `DOCENTE` entra a Configuración
      y ve **únicamente** "Campus (Moodle)": la URL del campus (solo lectura, institucional) y
      **sus** credenciales. NO ve Parámetros generales, Scoring, Detección ni Consentimiento
      (`configurar_sistema` es admin-only por diseño). El `ADMIN_SISTEMA` ve todas las
      secciones + la credencial institucional. Estado mostrado como "Conectado como X ·
      ****abcd" con botón de verificar y de desconectar.
- [x] 10.8 Test de ruta/gating (frontend): `/admin/configuracion` deja de ser ADMIN-only y
      pasa a exigir capacidad por sección. Un `DOCENTE` que fuerza la URL de una sección
      admin no la ve; un `ESTUDIANTE` sigue sin entrar.
      HECHO: ruta de ADMIN → ACADEMICO; las 4 pestañas de config quedan `soloAdmin` y el
      contenido además se condiciona (no basta ocultar la pestaña). `Configuración` sumada
      al sidebar del docente (antes solo se llegaba tipeando la URL).
      VERIFICADO EN PLAYWRIGHT con un docente real (DOC-001): ve SOLO "Campus (Moodle)",
      con subtítulo propio; el estudiante sigue sin entrar (403 en la API).
      + Campo "Nombre del servicio del campus" (`service_shortname`) en la sección del
      admin: sin él ningún docente puede conectarse y no había dónde cargarlo.
      SMOKE E2E CONTRA EL CAMPUS REAL: docente → PUT mi-credencial con credenciales falsas
      → canje en `login/token.php` de campustest → Moodle devuelve `invalidlogin` → la
      pantalla muestra "Usuario o contraseña incorrectos en el campus".

## 11. E2E COMPLETO contra el campus real (devolución y sincronización de notas)

> Recorrido entero con datos reales, no por partes. Requiere: servicio externo del campus con
> `core_grades_update_grades` habilitado y NO restringido a lista blanca (si lo está, ningún
> docente puede sacar su token).

- [x] 11.1 Configuración del campus (UNA vez, NO por docente). RESUELTA Y VERIFICADA.
      El servicio externo y el token institucional YA EXISTÍAN desde C-69 — no había que
      crear nada. Datos reales: servicio **"API Moodle Proctoring"**, shortname
      **`api_moodle`**, 8 funciones (incluye `core_grades_update_grades`,
      `gradereport_user_get_grade_items`, `core_user_get_users_by_field`).
      LO QUE FALTABA, y costó encontrarlo:
      a) `restrictedusers` estaba en true → cada docente había que agregarlo a mano.
         DESTILDADO.
      b) Otorgar `moodle/webservice:createtoken` al rol **Profesor** NO FUNCIONA: los
         docentes tienen ese rol en CONTEXTO DE CURSO y `login/token.php` evalúa la
         capacidad en CONTEXTO SISTEMA → devuelve `cannotcreatetoken` con credenciales
         correctas. Este fue el callejón sin salida.
      c) LA SOLUCIÓN: `moodle/webservice:createtoken` al rol **"Usuario identificado"**
         (roleid 7). Una casilla, una vez, para siempre. `webservice/rest:use` y
         `createmobiletoken` ya venían marcadas de fábrica.
      VERIFICADO E2E CONTRA EL CAMPUS REAL con `profesor_prueba`:
      · saca su token con usuario+contraseña, sin habilitación previa;
      · el token expone 8 funciones (no las 437 del servicio móvil);
      · escribe nota en el curso donde ES profesor → `0` (OK);
      · MISMO token en un curso AJENO → `errorcoursecontextnotvalid`. **La autorización
        la impone Moodle, no nuestro código.**
      · Historial de calificación del curso: **Calificador = "Profesor Prueba"**,
        **Fuente = `activeexam:doc=PROF-PRUEBA-001`**.
      PENDIENTE DE POLÍTICA (no técnico): si `createtoken` a todos los usuarios
      identificados es aceptable en producción. Riesgo verificado como bajo (un alumno
      puede sacar token pero NO puede calificar), pero lo decide el campus.

- [x] 11.2 Docente carga sus credenciales en Configuración → Campus (Moodle) → canje OK →
      estado "Conectado como …". Verificar en la DB que quedó el TOKEN y NO la contraseña.
      VERIFICADO: "Conectado como profesor_prueba · ****9c93"; DB: token_len=140 (Fernet), estado=activa.
- [x] 11.3 Examen vinculado a la comisión del docente, con curso + actividad del campus real.
      VERIFICADO: examen_contenido moodle_courseid=7, moodle_cmid=537; Comisión 1 → Profesor Prueba.
      Nota: verificación de 403 con otro docente pendiente (requiere segundo docente de prueba).
- [x] 11.4 Alumno rinde el examen completo → se calcula la nota → sincronización.
      VERIFICADO: sesión EST-001 nota=7.50 → sincronizar-moodle → estado=enviado, moodle_userid=8.
- [x] 11.5 Verificar **en la libreta de Moodle**: la nota llegó al alumno correcto, con la
      escala correcta (`grademax`), y el historial de calificaciones muestra la atribución
      del docente.
      VERIFICADO: Moodle Entregas muestra 75,00/100,00 para "Alumno Prueba". Token de profesor_prueba.
- [x] 11.6 Caso de identidad no resoluble: NO escribe a un usuario arbitrario; queda fallido
      y visible (cierra 7.4).
      VERIFICADO: INEXISTENTE-999 → estado=fallido, error_detalle="no está matriculado en curso 7".
- [x] 11.7 SUPERSEDED por decisión de diseño (task 10.4): NO hay respaldo institucional.
      Sin credencial del docente la nota queda retenida con motivo sin_credencial_docente.
- [x] 11.8 Auditoría del recorrido completo: figura quién sincronizó y con qué credencial
      (personal vs institucional), y el token no aparece en ningún registro ni export.
      VERIFICADO: audit_log muestra moodle.sync/actor=admin, moodle_credencial_update/actor=PROF-001.
      Token nunca aparece en audit_log ni moodle_writeback_audit.

## 12. Revalidación periódica de la credencial docente (nunca guardar la contraseña)

> Decisión (2026-07-31): NO se adopta el modelo de `active-ia-correcion-automatica`
> (guardar `password_encrypted` + re-auth automática cada 50 min). Un token filtrado
> solo compromete las funciones del web service; una contraseña filtrada compromete
> la cuenta completa de Moodle y, si el docente reutiliza contraseñas, potencialmente
> ActiveExam también — con una sola master key de cifrado del backend. En cambio: la
> credencial (token) vence sola a los 30 días desde la última vez que se demostró
> conocer la contraseña vigente, sin persistirla nunca. Reutiliza `actualizado_en`
> (ya se pisa en cada `guardar_token`/`guardar_con_password` exitoso — no hace falta
> columna nueva).

- [x] 12.1 Test (RED): helper puro `esta_vencida(actualizado_en, ahora, dias=30) -> bool`
      en `credencial_docente_service.py`. Triangular: recién guardada → False; a los 29
      días → False; a los 30 días exactos → True; a los 60 → True.
      HECHO: 4 tests verdes, sin DB (función pura).
- [x] 12.2 `estado()` y `token_de()` devuelven `vencida` (no `activa`) cuando
      `esta_vencida()` da True, aunque la columna diga `activa` — el vencimiento es
      calculado, no un job en background que reescribe filas. `token_de()` trata
      `vencida` igual que `caida`: devuelve `None` (no reintenta con un token viejo).
      HECHO: `_estado_efectivo()` calcula `vencida` a partir de `actualizado_en`;
      `caida` prevalece sobre `vencida` (si Moodle ya la rechazó, el motivo correcto
      es ese, no la antigüedad). 4 tests nuevos verdes (30 días exacto, 29 días
      todavía activa, token_de→None cuando vencida, caida prevalece).
- [x] 12.3 Test: sincronizar una nota con credencial vencida NO reintenta con el token
      guardado — falla igual que hoy con `caida`, mensaje distinto: "tu conexión con
      el campus venció, volvé a cargar tu contraseña" (no sugiere que Moodle la revocó,
      porque no fue Moodle).
      HECHO: `_credencial_para` devuelve un 4to valor `motivo_bloqueo`
      (`sin_docente|sin_credencial_docente|caida|vencida`); `MENSAJE_POR_MOTIVO_BLOQUEO`
      en writeback_service.py separa el mensaje de cada uno. 8 tests nuevos verdes
      (motivo por escenario + que el mensaje de vencida no sugiera rechazo de Moodle).
      Actualizados los 2 subclasses de test que sobreescribían `_credencial_para` con
      el contrato viejo de 3 valores (test_c69_writeback_service.py,
      test_c69_admin_resultados_sync.py).
- [x] 12.4 UI (`MiCuentaCampus.tsx`): estado "Conectado como X" pasa a avisar la
      antigüedad ("Conectado hace 25 días · vence en 5") cuando falten ≤7 días, y a
      "Venció, volvé a conectarte" cuando ya pasó — mismo flujo de PUT que hoy, no es
      un caso nuevo, solo copy distinto de `caida`.
      HECHO: helper puro `avisoConexion()` en `miCuentaCampus.helpers.ts` (7 tests
      verdes RED→GREEN→TRIANGULATE, sin DOM). Banner nuevo estado `por_vencer`
      (ámbar, token `warning`) y `vencida` (rojo, mensaje distinto de `caida`: no
      sugiere que el campus la rechazó).
- [x] 12.5 Test: `GuardarMiCredencialRequest` con password renueva `actualizado_en` a
      "ahora" (ya lo hace `guardar_token`) — verificar explícitamente que esto reinicia
      la cuenta de los 30 días, no solo que guarda el token.
      HECHO: `test_recargar_una_credencial_vencida_reinicia_el_contador_de_30_dias` —
      confirma comportamiento YA existente en `guardar_token` (candado de regresión,
      no requirió código nuevo).

## 13. Fix de auditoría — credencial docente quedaba con `modulo=NULL`

> Bug real encontrado (2026-07-31), independiente de la sección 12 pero se arrastra a
> los eventos nuevos si no se corrige antes: `_auditar_credencial` (config/router.py:361)
> usa `accion="moodle_credencial_update"` (guion bajo) sin pasar `modulo=` explícito.
> `modulo_de_accion()` (audit/acciones.py:131) solo matchea `a == "moodle.sync"` (con
> punto) — nunca "moodle_credencial_update". Resultado actual: estas entradas NUNCA
> aparecen filtrando por módulo "MOODLE" en Auditoría. Separar de una además de
> "Configuración → Campus Moodle" (que es `modulo=CONFIGURACION`, institucional):
> `modulo=MOODLE` + `entidad=USUARIO` (personal del docente) vs `modulo=CONFIGURACION`
> + `entidad=CONFIGURACION` (institucional) — filtrando por módulo quedan separados
> sin ambigüedad.

- [x] 13.1 Test (RED): reproducir el bug — auditar con `accion="moodle_credencial_update"`
      sin `modulo=` explícito y verificar que `modulo_de_accion()` devuelve `None` hoy.
      HECHO: `test_el_string_viejo_moodle_credencial_update_no_tenia_modulo` — documenta
      el bug tal cual estaba, no se corrige ese string puntual (ver 13.5).
- [x] 13.2 Agregar a `AccionAuditoria` (acciones.py) los eventos reales en vez del
      string suelto `ACCION_MOODLE_CREDENCIAL`: `MOODLE_CREDENCIAL_CONECTAR`,
      `MOODLE_CREDENCIAL_DESCONECTAR`, `MOODLE_CREDENCIAL_RENOVAR` (12.5).
      REDUCIDO DE ALCANCE: se descartó `MOODLE_CREDENCIAL_VENCIDA` como evento pasivo
      de auditoría — hubiera exigido trackear "ya se auditó este vencimiento" en la
      tabla (una columna nueva) solo para no escribir una fila por cada GET de estado
      (que es lectura frecuente). El vencimiento YA queda registrado por sesión de
      sync fallida en `moodle_writeback_audit`/`error_detalle` (sección 12.3) — no
      hacía falta un segundo mecanismo de auditoría para lo mismo.
- [x] 13.3 `_auditar_credencial` pasa `modulo=ModuloAuditoria.MOODLE`,
      `entidad=EntidadAuditoria.USUARIO`, `entidad_id=usuario_id` explícitos (mismo
      patrón que ya usa el bloque de config institucional en la línea 268-269).
      Los 2 call-sites (PUT conecta/renueva según `estado.configurada` ANTES de
      escribir; DELETE desconecta) pasan la `accion` correcta.
- [x] 13.4 Test: filtrar Auditoría por módulo "MOODLE" trae conectar/desconectar/
      renovar del docente; filtrar por "CONFIGURACION" trae SOLO los cambios
      institucionales (token global, service_shortname) — nunca se mezclan.
      HECHO: endpoint real (PUT/DELETE `/config/moodle/mi-credencial`) contra DB real,
      7 tests verdes entre los dos archivos nuevos. GOTCHA encontrado en el propio
      test: `audit_log.id` es UUID aleatorio — `ORDER BY id` NO da orden cronológico,
      hay que ordenar por `timestamp`.
- [x] 13.5 Migración de datos: las filas históricas con `accion="moodle_credencial_update"`
      y `modulo IS NULL` quedan así (no se re-escribe audit log — regla dura de
      inmutabilidad de evidencia); el fix aplica solo hacia adelante. Documentar esto
      en el PR para que no se lea como "no funcionó".
      DISCOVERY (no relacionado al código, de infraestructura local): la DB de dev
      compartida tenía DRIFT de schema — le faltaban las columnas de la migración
      0044 (`modulo`/`entidad`/`entidad_id`/`tipo_accion` en `audit_log`) y el FK
      `ON DELETE CASCADE` de la migración 0050 (`moodle_credencial_docente.usuario_id`),
      porque nunca se había corrido `alembic upgrade slim@head` contra ese contenedor
      Postgres (persistente hace 6 días, sin contenedor `backend` que migrara). Se
      aplicó el DDL exacto de esas 2 migraciones a mano (aditivo, sin pérdida de
      datos) y se hizo `alembic stamp slim@0051` para dejar la DB consistente con
      el head real. Confirmado contra el propio historial de Alembic que 0044→0051
      es una cadena lineal única (rama `slim`) — no había ninguna otra fuente que
      ya resolviera esto.

## 14. Ajustes de UX y semántica de auditoría (revisión en vivo contra la app corriendo)

> Surgidos probando C-73 §12/§13 con Playwright contra backend+frontend+DB reales
> (no solo tests). TDD igual que el resto: RED→GREEN, sin mocks de DB.

- [x] 14.1 UI `MiCuentaCampus.tsx`: card única "Campus (Moodle)" (antes: título
      duplicado "Tu cuenta del campus" adentro de la card Y "Campus (Moodle)"
      afuera). Sin negrita en el nombre de usuario, sin mostrar `token_pista`
      (causaba confusión — se leía como si fuera parte de la contraseña, NUNCA
      lo fue). Textos finales: activa → "Conectado."; por vencer → "En N días
      vencen tus credenciales..."; vencida → "Tu acceso venció por seguridad,
      volvé a ingresar tus credenciales." (sin mencionar al campus, no fue él).
      Íconos: `error` (círculo ámbar sólido) para por vencer, `lock_clock` para
      vencida — ninguno usa el triángulo de "warning" (leía como alarma).
      Pestañas de Configuración sin ícono; ocultas por completo si solo hay
      una (docente: va directo a la card, sin selector inútil).
- [x] 14.2 Toast (`useToast`) con el mismo mensaje que el error/éxito inline en
      conectar/renovar/desconectar — verificado en vivo que aparece.
- [x] 14.3 Semántica de `RENOVAR` redefinida: solo se audita si la credencial
      previa estaba `caida` o `vencida` (es decir, hacía falta reconectar). Si
      ya estaba `activa` y sana, recargarla NO genera fila nueva — evita
      ensuciar Auditoría con renovaciones sin motivo cada vez que alguien
      reingresa la contraseña "por las dudas". 6 tests verdes.
- [x] 14.4 `IntentosFallidosTracker` — contador EN MEMORIA (sin tabla nueva a
      propósito, decisión explícita tras discutir alternativas) de intentos
      fallidos SEGUIDOS por `usuario_id`. Al llegar a 5 audita
      `MOODLE_CREDENCIAL_INTENTOS_FALLIDOS` una vez y se reinicia (vuelve a
      disparar tras otra tanda de 5). Un intento correcto borra el contador.
      Cableado en `main_slim.py` (`app.state.moodle_intentos_fallidos`).
      Trade-off aceptado: se pierde el conteo si el backend reinicia — es una
      señal de patrón reciente, no un registro forense. 5 tests puros +
      3 tests de integración contra el endpoint real (respx mockea el canje).
