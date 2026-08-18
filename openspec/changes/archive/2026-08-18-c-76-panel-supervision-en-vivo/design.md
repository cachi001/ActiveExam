# Design — c-76 Panel de supervisión en vivo (rediseño de roles + UX)

## Context

El panel de supervisión funcional se entregó en C-15 (activeexam: REST + polling, sin SSE). Su transporte de tiempo real de producción vive en **c-15b** (bloqueado por C-03). Este change **no toca transporte** ni depende de C-03: rediseña el **modelo de roles** que gobierna el panel y la **UX** de tres pantallas.

Estado actual relevante:
- `Rol` (`backend/app/domain/auth/roles.py`) tiene 8 valores, incluido `PROCTOR`. `ROLES_CON_MFA` lo incluye.
- `CAPABILITY_ROLES["supervisar_vivo"]` = `{PROCTOR, REVISOR, COORDINADOR, ADMIN_SISTEMA}`.
- `revisar_sesion` (veredicto terminal, un solo paso) = `{REVISOR, COORDINADOR, ADMIN_SISTEMA}`. Ya excluye a proctor.
- `asignar_docente` (C-73 §9) modela la pertenencia tutor↔comisión; el tutor no puede auto-asignarse.
- `chat_pausa_service.py`: chat bidireccional + pausas. La pausa la resuelve un `proctor_actor`; **no** hay límite de cantidad de pausas, solo timeout del pedido (120s, env `PAUSA_REQUEST_TIMEOUT_SEG`). El audit trail es la propia fila `pausa_autorizada`.
- `GestionUsuarios.tsx:165`: `POST /users` devuelve `password_generada` y hoy se muestra en un `toast.success` efímero.

Governance: la eliminación de un rol del enum es **Auth/RBAC = CRÍTICO**. Este change **solo diseña**; la implementación de la parte RBAC requiere aprobación humana explícita antes de escribir (ver Migration Plan).

## Goals / Non-Goals

**Goals**
- Eliminar `PROCTOR` del dominio sin dejar referencias colgadas ni over-permisos.
- Que el TUTOR supervise en vivo y vea el registro **solo de sus comisiones**, sin poder de veredicto.
- Chat y pausas tutor↔alumno; alumno no inicia chat; tutor aprueba pausas con límite configurable (default 2).
- Screenshots del alumno durante la pausa.
- Rediseño de la pantalla de detalle de sesión (con/sin riesgo; tutor vs coordinador).
- UX: alta de usuario con clave temporal persistente + copiable; subida de nota individual y en lote con selección; columna de acciones sticky.

**Non-Goals**
- **No** implementar transporte SSE / tiempo real de producción (eso es c-15b, post-C-03).
- **No** cambiar el contrato de `POST /users` (ya devuelve `password_generada`).
- **No** introducir una segunda instancia de veredicto ni "caso abierto" (el owner ya lo rechazó; veredicto es un solo paso).
- **No** implementar código en este change (esto es el propose).
- **No** renombrar los archivos de spec `proctor-*` en disco (se actualiza contenido por delta; el rename físico se evalúa aparte para no romper referencias de archive).

## Decisions

### D1 — Eliminar PROCTOR directamente, no fusionar/renombrar
`COORDINADOR` ya existe y ya tiene `revisar_sesion`. Sacar `PROCTOR` del enum y reasignar `supervisar_vivo` a `{TUTOR (acotado), REVISOR, COORDINADOR, ADMIN_SISTEMA}`. **Alternativa descartada**: renombrar `PROCTOR`→algo; se descarta porque coordinador ya cubre la supervisión global y el tutor cubre la acotada — un rename dejaría un tercer actor sin puesto institucional real.

### D2 — Supervisión del tutor acotada por comisión (reuso de C-73)
El tutor tiene `supervisar_vivo` pero el acceso a una sesión concreta se filtra por la pertenencia `asignar_docente` (comisión de la que es docente). Se resuelve como **doble control**: capability (rol lo habilita) + scope contextual (comisión). **Alternativa descartada**: dar al tutor supervisión global como coordinador — viola separación de funciones (quien pone la nota no debe supervisar exámenes ajenos).

### D3 — El tutor NUNCA emite veredicto
`revisar_sesion` **no** incorpora `TUTOR`. El panel de detalle renderiza el botón de veredicto **solo** si el usuario tiene `revisar_sesion` (coordinador/revisor/admin). El tutor ve el mismo dossier en modo lectura de decisión. Esto mantiene la regla dura #5 (veredicto siempre humano y aquí, además, humano-con-autoridad-separada).

### D4 — Chat tutor↔alumno; alumno solo responde
El autor de mensaje pasa de `proctor`/`alumno` a `tutor`/`alumno`. Regla nueva de negocio: **el alumno no puede crear el primer mensaje** de un hilo — solo puede responder si ya existe al menos un mensaje del tutor en esa sesión. Se valida server-side (no confiar en el cliente). **Alternativa descartada**: permitir al alumno iniciar — el owner lo prohíbe (evita spam/distracción y canal de fuga).

### D5 — Límite de pausas configurable, default 2
Nuevo umbral en Configuración del Sistema (capability `system-configuration` / `effective-config-consumption`), leído por el servicio al **aprobar** (no al solicitar): si la sesión ya tiene N pausas en estado `aprobada`/`finalizada` >= límite, aprobar devuelve 409/estado-inválido con mensaje claro. Default 2. Se lee de la config efectiva, no de env hardcodeado. **Alternativa descartada**: limitar al solicitar — se prefiere limitar al aprobar para que el alumno siempre pueda pedir y quede el rastro del pedido rechazado por límite.

### D6 — Screenshots durante la pausa
Durante una ventana `aprobada`, el cliente sube screenshots del alumno con cadencia configurable; se persisten como evidencia (patrón `screenshot-evidence-capture` ya existente en el proyecto). Regla #6: el screenshot es dato de cliente → se hashea/firma server-side; su ausencia es en sí una señal (no bloquea, pero queda registrada). No suma automáticamente al score (L2.5): es insumo de revisión humana.

### D7 — Alta de usuario: página dedicada + modal (no toast)
Ruta nueva `/admin/usuarios/nuevo`: formulario dedicado. Al crear, si el backend devuelve `password_generada`, se abre un **modal** con: la clave en grande, botón "copiar" (`navigator.clipboard`), aviso "guardala, no la vas a volver a ver" y "el usuario deberá cambiarla en el primer ingreso". El toast efímero de `GestionUsuarios.tsx:165` se elimina para este flujo. Patrón de referencia interno ya validado en otro sistema (página + modal de credencial temporal). **Alternativa descartada**: seguir con toast — se pierde la clave, es el bug que motiva la tarea.

### D8 — Subida de nota: individual + lote con selección
Tabla de notas: (a) etiqueta de botón clara en vez de "sincronizar con Moodle"; (b) acción de subir nota **por fila** (individual); (c) **checkbox** por fila + acción "subir seleccionadas" para lote. La capability de escritura de nota ya existe (`gestionar_notas` / `moodle-grade-writeback`); esto es UX sobre esa acción, sin cambiar la autoridad (tutor/coordinador/admin).

### D9 — Columna de acciones sticky
CSS: la última columna (acciones) queda `position: sticky; right: 0` con fondo y sombra, siempre visible en scroll horizontal. Patrón puramente presentacional, reutilizable en otras tablas.

### D10 — Validación `nota_aprobacion ≤ nota_maxima` en el schema (defensa en profundidad, governance BAJO)
La invariante ya se aplica imperativamente en dos routers (`catalog_router.py`: creación desde banco lanza 422 si `nota_aprobacion > nota_maxima`; PATCH de config delega en `validar_config_examen` de `domain/exam_content/config.py`, que valida `0 <= nota_aprobacion <= nota_maxima`) y en el frontend. **Gap**: no está declarada en el schema Pydantic, así que un endpoint nuevo que reciba estos campos podría omitir el chequeo. Se agrega un `model_validator(mode="after")` en `CrearDesdebancoRequest` y `ActualizarConfigRequest` (ambos con `extra='forbid'`) que rechaza `nota_aprobacion > nota_maxima` con 422. En el PATCH parcial, la validación cruzada del schema solo dispara si **ambos** campos vienen en el cuerpo; la coherencia sobre los valores finales mergeados sigue cubierta por `validar_config_examen` (que NO se elimina — se mantiene la doble red). Governance BAJO: hardening puro, contrato HTTP sin cambios (mismo 422), full autonomía con tests en verde. **Alternativa descartada**: mover la lógica del router al schema y borrar el chequeo imperativo — se descarta para no perder el mensaje de error específico del router ni la validación de dominio del merge; se prefiere sumar una red, no reemplazar.

### D11 — Deploy cleanup: remover Keycloak, conservar el modo alternativo del código (governance MEDIO)
El auth productivo es JWT propio (`auth_provider="jwt"` default en `app/config.py`, `own_issuer` de C-55) + login local. Keycloak permanece en el deploy (servicio en `docker-compose.yml`, `depends_on` de `api`, envs `KEYCLOAK_*`/`KC_*`, `infra/keycloak/`, placeholders `.env`) pero no es una pieza operativa en uso. Se remueven esas piezas de **deploy/config**. Se **conserva** el código que soporta `auth_provider="keycloak"` (settings `keycloak_*` en `app/config.py`, validador multi-issuer): es la abstracción de proveedor de C-55, capacidad de dominio, no config muerta. Governance MEDIO → **el relevamiento de qué está realmente sin uso es el primer paso (task 12.1) antes de borrar**; ante duda, se deja como Open Question (Q7) y no se borra. **Alternativa descartada**: arrancar borrando el servicio del compose sin relevar — riesgo de romper un flujo dev/staging que aún dependa de Keycloak; por eso relevamiento primero.

## Risks / Trade-offs

- **[Datos con rol `proctor` en la DB/Keycloak]** → Migración explícita: relevar usuarios con rol `proctor`, remapear a `coordinador` (supervisión global) o `tutor` (docente de comisión) según su función real; ninguno queda huérfano. Paso de datos separado del cambio de código, con aprobación humana (CRÍTICO).
- **[JWT con claim `proctor` en circulación]** → Hoy `parse_rol` descarta roles desconocidos silenciosamente; tras el cambio, un token viejo con `proctor` pierde el acceso al panel sin error de sistema. Aceptable en re-login; documentar en runbook. (Ver Open Questions Q1.)
- **[Referencias colgadas a `Rol.PROCTOR`]** → Búsqueda exhaustiva de `PROCTOR`/`"proctor"` en backend antes de mergear; tests de RBAC que hoy asuman proctor deben migrarse (sin mocks de DB, regla dura #4).
- **[Tutor viendo sesiones fuera de su comisión]** → El filtro por `asignar_docente` es la barrera; sin él, `supervisar_vivo` daría acceso global. Tests contextuales obligatorios (autorizado en su comisión / 403 fuera de ella).
- **[Screenshot como falsa tranquilidad]** → Registrar la screenshot NO reemplaza el juicio humano; ausencia de captura durante pausa es señal, no veredicto (L2.5).
- **[Clave temporal visible en cliente]** → El modal la muestra una sola vez; no se persiste en estado global ni logs. Copiar usa clipboard del navegador.

## Migration Plan

1. **(CRÍTICO — requiere aprobación humana antes de código)** Relevar en la DB/IdP los sujetos con rol `proctor`. Definir mapa de remapeo (proctor→coordinador o proctor→tutor). 
2. Migración de datos (Alembic si aplica a tabla de roles local; en Keycloak, reasignación de roles) — destructiva en dos pasos (regla del proyecto).
3. Cambio de código: quitar `PROCTOR` del enum y de `ROLES_CON_MFA`; actualizar `supervisar_vivo`.
4. Backend chat/pausa: actor `tutor`, regla "alumno no inicia", límite configurable, screenshots.
5. Config del sistema: nuevo umbral `pausas_max_por_sesion` (default 2).
6. Frontend: nueva ruta de alta + modal; rediseño detalle; UX notas; columna sticky; acotado por comisión del tutor.
7. **Rollback**: como el enum es dato de dominio, revertir el commit restaura `PROCTOR`; los datos remapeados NO se revierten automáticamente — de ahí que el remapeo se documente para poder deshacerlo manualmente. La UX es aditiva/rollback-safe.

## Open Questions

- **Q1**: ¿Los JWT viejos con claim `proctor` deben rechazarse activamente (error) o seguir descartándose en silencio (`parse_rol` actual)? Asunción: mantener el comportamiento tolerante actual (silencioso); revisar con seguridad si se prefiere invalidación explícita.
- **Q2**: ¿El límite de pausas cuenta también las `rechazadas`/`expiradas` o solo `aprobada`+`finalizada`? Asunción: solo `aprobada`+`finalizada` (las que efectivamente ocurrieron).
- **Q3**: Cadencia de screenshots durante la pausa: ¿reusa la cadencia global de `evidence-capture-cadence` o una específica de pausa? Asunción: reusar la global existente salvo que el owner pida una específica.
- **Q4**: ¿Se renombran físicamente los specs `proctor-*` a `supervision-*` o solo se actualiza su contenido? Asunción: solo contenido (delta) en este change, para no romper referencias de archive; rename físico como tarea de higiene aparte.
- **Q5**: ¿El coordinador conserva supervisión **global** (todas las comisiones) mientras el tutor queda acotado? Asunción: sí — coordinador global, tutor por comisión.
- **Q6**: La validación cruzada de nota en PATCH, ¿debe cubrir también el caso "solo mando `nota_aprobacion` y sube por encima del `nota_maxima` persistido"? Asunción: NO a nivel schema (no ve el valor persistido); ese caso lo cubre `validar_config_examen` sobre el merge en el router. El schema solo valida cuando ambos campos vienen en el cuerpo.
- **Q7**: ¿Hay algún flujo dev/staging que todavía dependa de Keycloak (por ejemplo un entorno con `auth_provider=keycloak`)? El relevamiento (task 12.1) lo confirma antes de borrar. Asunción: no en producción; si aparece uno, la pieza correspondiente NO se borra y queda documentada.

## Resolución de Open Questions al implementar (bloques 4/5/6/8/9)

- **Q2 (confirmada)**: el límite de pausas (`pausas_max_por_sesion`) cuenta SOLO `aprobada`+`finalizada`. Implementado así en `chat_pausa_service._contar_pausas_consumidas`; cubierto por `test_pausas_rechazadas_no_cuentan_para_el_limite`.
- **Q3 (parcialmente resuelta, con desvío documentado)**: no se implementó una cadencia de captura DEDICADA a la pausa en el cliente. En su lugar: (a) el backend define el tipo de evento `captura_pausa` (BASELINE) para cuando el cliente lo emita, reusando el pipeline general de eventos (re-hash/firma ya existentes); (b) al cerrar la ventana de pausa (`finalizar_pausa`), el backend verifica si hubo al menos una captura `captura_pausa` en la ventana y, si no, emite `pausa_sin_captura` (BASELINE) como señal — sin bloquear ni sancionar (L2.5). **Lo que falta como follow-up**: cablear en el cliente (`useExamProctoring.ts` / `PausaAlumno.tsx`) la emisión explícita de eventos `captura_pausa` con cadencia propia durante la ventana `aprobada`. Hoy la detección general sigue corriendo durante la pausa (decisión previa ya documentada en `PausaAlumno.tsx`), pero no etiqueta nada como `captura_pausa`, por lo que `pausa_sin_captura` se dispara siempre hasta que se complete ese follow-up.
- **Q5 (confirmada y extendida)**: coordinador es global. Se agregó explícitamente que **REVISOR también es de alcance institucional** (no estaba upradicado como pregunta abierta, pero surgió al implementar D2): `autorizar_supervision_vivo_sobre_sesion` exime a `{COORDINADOR, REVISOR, ADMIN_SISTEMA}` del scoping por comisión — solo TUTOR queda acotado. Razón: REVISOR ya operaba en alcance global antes de este change (cola de revisión no está particionada por comisión) y `revisar_sesion` no incluye a TUTOR.
- **Decisión no obvia fuera de Q1–Q7 (D4/bloque 6)**: el campo `proctor_actor` de `PausaResolverIn`/`PausaDetalle`/`PausaPendiente` (schemas de chat/pausa) **se mantuvo con ese nombre** aunque el actor conceptual pasó de "proctor" a "tutor" (D4). Renombrarlo hubiera sido un cambio de contrato HTTP más amplio (afecta al frontend `PausaSesionPanel`/`ObservacionesProctor` y no aporta corrección — es solo un identificador de auditoría). Se documenta acá para que quede explícito el desvío; renombrar el campo queda como tarea de higiene aparte si se decide.
