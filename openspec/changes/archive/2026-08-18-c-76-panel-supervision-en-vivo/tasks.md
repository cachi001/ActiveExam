# Tasks — c-76 Panel de supervisión en vivo

> Orden por dependencia. **Bloque B (UX) va primero** por pedido del dueño: la tarea 1 (alta de usuario + modal) es la primera implementable. El Bloque A (roles) va después porque su parte RBAC es CRÍTICA y requiere aprobación humana antes de tocar código (ver design §Migration Plan).
>
> Reglas duras aplicables a TODAS las tareas: tests sin mocks de DB (base real/efímera), Pydantic `extra='forbid'`, snake_case Python, PascalCase componentes React, el sistema NUNCA sanciona automático, veredicto siempre humano.

## 1. Alta de usuario con clave temporal (Bloque B — PRIMERA)

- [x] 1.1 Crear página dedicada de alta `/admin/usuarios/nuevo` (componente `UsuarioCreate.tsx`, PascalCase) con formulario de alta, protegida por capacidad `gestionar_usuarios`
- [x] 1.2 Al crear, invocar `POST /users` existente (sin cambiar contrato) y capturar `password_generada` de la respuesta
- [x] 1.3 Implementar modal post-creación que muestra la clave temporal con botón copiar (`navigator.clipboard`) y los avisos "guardala, no la vas a volver a ver" / "el usuario deberá cambiarla en el primer ingreso"
- [x] 1.4 Eliminar el toast efímero de clave en `GestionUsuarios.tsx` (línea ~165) y enlazar el flujo de alta a la nueva página; no persistir la clave en estado global ni logs
- [x] 1.5 Tests: acceso denegado sin `gestionar_usuarios`; modal aparece solo cuando hay `password_generada`; sin clave generada no hay modal de clave

## 2. UX de subida de nota (Bloque B)

- [x] 2.1 Renombrar la etiqueta del botón "sincronizar con Moodle" por una etiqueta clara de subir/publicar nota
- [x] 2.2 Agregar acción de subir nota individual por fila
- [x] 2.3 Agregar checkbox por fila + selección múltiple + acción "subir seleccionadas" (lote)
- [x] 2.4 Manejar el caso de lote sin selección (no publica, avisa)
- [x] 2.5 Tests de UX/lógica de selección (individual y lote) sin cambiar la autoridad `gestionar_notas`

## 3. Columna de acciones sticky (Bloque B)

- [x] 3.1 Hacer la última columna (acciones) `sticky` (`position: sticky; right: 0`) con fondo/sombra en la tabla de notas y demás tablas anchas relevantes
- [x] 3.2 Verificar que sin scroll horizontal el layout no se rompe (sin artefactos)

## 4. Límite configurable de pausas (Bloque A — backend, no toca RBAC)

- [x] 4.1 Agregar umbral `pausas_max_por_sesion` (default 2) al schema de Configuración del Sistema (`extra='forbid'`), editable por `configurar_sistema`
- [x] 4.2 Consumir el umbral desde la configuración efectiva en `chat_pausa_service.py` al **aprobar** una pausa; rechazar la aprobación si la sesión ya tiene `aprobada`+`finalizada` >= límite
- [x] 4.3 Exponer/editar el umbral en la UI de Configuración del Sistema
- [x] 4.4 Tests: default 2; aprobación rechazada por límite; el alumno siempre puede solicitar; solo admin lo configura

## 5. Screenshots durante la pausa (Bloque A — backend + cliente)

- [x] 5.1 Cliente: capturar y subir screenshots del alumno durante ventana de pausa `aprobada` (reusar cadencia de captura existente salvo decisión contraria — ver Open Question Q3). Implementado y VERIFICADO: `crearControladorCapturaPausa` (`useExamProctoring.ts`) postea `tipo=captura_pausa` cada `PAUSA_CAPTURA_INTERVAL_MS` (30s, reusa `HEARTBEAT_MAX_FREQ_SEC`) mientras `setPausaAprobada(true)`; captura inmediata al activar, cleanup en `detener()`. Cableado desde `Examen.tsx` vía el mismo callback `onActivaChange` de `PausaAlumno`. Tests: `useExamProctoring.pausaCaptura.test.ts` (6✓).
- [x] 5.2 Backend: persistir screenshots vinculados a sesión + ventana de pausa, re-hasheados/firmados server-side (regla #6) — reusa el pipeline general de eventos (ya re-hashea/firma), tipo nuevo `captura_pausa` (BASELINE)
- [x] 5.3 Asegurar que las capturas NO suman automáticamente al score (L2.5); ausencia queda como señal — `TipoEvento.CAPTURA_PAUSA`/`PAUSA_SIN_CAPTURA` en BASELINE + exclusión por ventana de pausa (doble red); `finalizar_pausa` emite `pausa_sin_captura` server-side si no hubo captura en la ventana
- [x] 5.4 Tests: captura persistida y firmada; ausencia registrada como señal sin veredicto; score no afectado automáticamente (`tests/proctoring/test_c76_pausa_screenshots.py`)

## 6. Chat y pausas tutor↔alumno (Bloque A — backend)

- [x] 6.1 Cambiar el actor de chat/pausa de `proctor` a `tutor` en `chat_pausa_service.py` y routers de chat/pausa (literal `MensajeChatIn.autor`; el campo `proctor_actor` de `PausaResolverIn`/`PausaDetalle` se CONSERVA por compatibilidad — ver decisiones no obvias del resumen de cierre)
- [x] 6.2 Regla server-side: el alumno NO puede iniciar el hilo; solo responde si ya existe un mensaje del tutor en la sesión (`AlumnoNoPuedeIniciarError` → 403)
- [x] 6.3 Aprobación/rechazo de pausa por el tutor, acotado a su comisión; audit trail en la fila `pausa_autorizada` con actor tutor (`autorizar_supervision_vivo_sobre_sesion`, D2)
- [x] 6.4 Tests: tutor inicia y alumno responde; alumno no puede iniciar; tutor de comisión ajena rechazado (403) (`tests/proctoring/test_c76_tutor_comision.py`, `tests/proctoring/test_chat_api.py`)

## 7. Eliminación del rol PROCTOR (Bloque A — RBAC, CRÍTICO)

> ⚠️ CRÍTICO (Auth/RBAC). Requiere **aprobación humana explícita** antes de escribir código (design §Migration Plan). No mergear sin migración de datos definida.

- [x] 7.1 Relevar sujetos con rol `proctor` en la DB/IdP y definir el mapa de remapeo (proctor→coordinador / proctor→tutor) — **aprobación humana**. Relevamiento: único sujeto sembrado con rol `proctor` es el usuario de seed `PROC-001` (`backend/scripts/seed_users.py`). Mapa aprobado por el dueño: **proctor → coordinador** (COORDINADOR absorbe supervisión global + veredicto).
- [x] 7.2 Migración de datos (destructiva en dos pasos) que remapea los roles `proctor` existentes → `backend/migrations/versions/0068_c76_remap_proctor_coordinador.py` (down_revision 0067, hereda branch `activeexam`). UP: `usuario.roles` JSONB "proctor"→"coordinador" sin duplicar (jsonb_agg DISTINCT), idempotente. DOWN: no-op documentado (remapeo irreversible de forma segura). No es DROP de esquema, por eso no requiere el patrón físico de dos pasos — documentado en el docstring.
- [x] 7.3 Eliminar `Rol.PROCTOR` del enum `Rol` y de `ROLES_CON_MFA` (`backend/app/domain/auth/roles.py`)
- [x] 7.4 Actualizar `CAPABILITY_ROLES["supervisar_vivo"]` a `{TUTOR, REVISOR, COORDINADOR, ADMIN_SISTEMA}` (`capabilities.py`); confirmado que `revisar_sesion` = `{REVISOR, COORDINADOR, ADMIN_SISTEMA}` (NO incluye `TUTOR`)
- [x] 7.5 Buscar y limpiar toda referencia colgante a `PROCTOR`/`"proctor"` en backend y tests (remap → coordinador). App: `authorization.py` (autorizar_proctor + set de evidencia), `enrollment/router.py`, `consent/router.py`, `exam_content/_shared.py`, `scripts/seed_users.py`. Tests: 8× `proctoring/*`, `test_auth_*`, `test_c55_*`, `test_c56/c59/c61/c63`, `test_users_filtros_reactivar`. Se DEJARON los strings `'proctor'` de chat/pausa (dominio de mensajería, Tarea 6).
- [x] 7.6 Tests RBAC (`tests/test_c76_eliminacion_rol_proctor.py`): `supervisar_vivo` sin `proctor`; tutor tiene `supervisar_vivo` pero no `revisar_sesion`; JWT con claim `proctor` no mapea a rol de dominio (descarte silencioso, Q1)

## 8. Supervisión del tutor acotada por comisión (Bloque A)

- [x] 8.1 Filtrar el acceso del tutor a sesiones/detalle/pausas por pertenencia `asignar_docente` (C-73 §9); coordinador queda global (`GET /sessions`, `GET /sessions/{id}`, `PATCH /pausas/{id}`)
- [x] 8.2 Acotar el listado de supervisión en vivo (`Proctor.tsx`) del tutor a sus comisiones — sin cambios de UI necesarios: `Proctor.tsx` consume `GET /sessions`, ya scoped server-side (regla dura #6, cliente no confiable — el scoping vive en el backend, no en el front)
- [x] 8.3 Tests contextuales: tutor autorizado en su comisión; 403 fuera de ella; coordinador ve todo (`tests/proctoring/test_c76_tutor_comision.py`)

## 9. Rediseño visual del detalle de sesión (Bloque A — frontend)

- [x] 9.1 Rediseñar `ProctoringSessionDetail.tsx` / `SessionDetail.tsx` para ambos estados (con riesgo / sin riesgo). Implementado: nuevo `RiesgoBanner.tsx` (siempre visible, no solo en cola de revisión) con tres variantes por `nivelRiesgo(score)` — bajo (confirmación discreta, verde), medio (aviso ámbar) y alto (alerta roja, `role="alert"`) — reusando la misma paleta que ya usan las listas (`scoreSoftBg`/`scoreSoftBorder` de `helpers.ts`, sin inventar tokens nuevos). La card de "Eventos de la sesión" también hereda el tinte de borde por riesgo, coherente con `SesionCard`/`SesionVivoCard`.
- [x] 9.2 Renderizar el botón de veredicto SOLO si el usuario tiene `revisar_sesion` (coordinador/revisor/admin); el tutor ve el dossier en modo lectura de decisión — `DecisionRevisorForm.tsx`: antes el botón "Aprobar con nota" quedaba visible/habilitado igual sin `puedeResolver` (el backend lo rechazaba con 403); ahora el componente entero cae a un dossier de solo lectura sin ningún control de veredicto
- [x] 9.3 Mostrar chat tutor↔alumno, pausas (con límite/estado) y screenshots de pausa en el detalle — `ChatBox` renombrado a actor `tutor` (ya mostraba pausas vía `PausaSesionPanel`/`PausasHistorial`; el histórico ya expone `en_pausa_autorizada` por evento)
- [x] 9.4 Tests de render diferenciado tutor (sin veredicto) vs coordinador (con veredicto) (`DecisionRevisorForm.test.tsx`)

## 11. Validación backend `nota_aprobacion ≤ nota_maxima` (Bloque C — governance BAJO)

> Defensa en profundidad: la invariante ya se aplica imperativamente en routers y dominio; acá se declara en el schema. Governance BAJO: full autonomía con tests en verde. Tests sin mocks de DB (regla dura #4).

- [x] 11.1 Agregar `model_validator(mode="after")` en `CrearDesdebancoRequest` (`backend/app/presentation/api/v1/exam_content/schemas.py`) que rechace `nota_aprobacion > nota_maxima`; mantener `extra='forbid'`
- [x] 11.2 Agregar la misma validación cruzada en `ActualizarConfigRequest` (PATCH de config), disparando SOLO cuando ambos campos vienen presentes en el cuerpo (evitar falso 422 en PATCH parcial); mantener `extra='forbid'`
- [x] 11.3 Confirmar que `validar_config_examen` (dominio) se conserva intacto — la validación de schema es red adicional, no reemplazo
- [x] 11.4 Tests (sin mocks de DB): 422 en creación con `nota_aprobacion > nota_maxima`; alta OK con `nota_aprobacion ≤ nota_maxima`; PATCH con un solo campo no dispara la validación cruzada del schema; campo no declarado sigue devolviendo 422 por `extra='forbid'`

## 12. Deploy cleanup — remover Keycloak (Bloque D — governance MEDIO)

> ⚠️ Governance MEDIO: **relevamiento primero**, borrado después. Es limpieza de CONFIG/deploy, NO toca dominio. NO borrar nada en uso; ante duda, dejar como Open Question (Q7) y NO borrar. NO tocar `backend/app/config.py` (settings `keycloak_*` = modo alternativo de C-55).

- [x] 12.1 **Relevamiento (paso previo, obligatorio)**: confirmar que ninguna pieza de deploy Keycloak está en uso (no hay entorno dev/staging con `auth_provider=keycloak`); listar exactamente qué se remueve vs. qué se conserva. Ante duda → Q7, no se borra
- [x] 12.2 Remover el servicio `keycloak` de `infra/docker-compose/docker-compose.yml`, su `depends_on` en el servicio `api`, el mapeo de puerto 8080 y las envs `KEYCLOAK_*`/`KC_*` del compose
- [x] 12.3 Remover los artefactos de `infra/keycloak/` no usados (`Dockerfile`, `proctoring-realm.json`, `railway.json`) y cualquier referencia a ellos
- [x] 12.4 Remover placeholders `KEYCLOAK_*`/`KC_*` de las plantillas de entorno (`.env.example` y demás plantillas de deploy) que no correspondan a una pieza levantada
- [x] 12.5 Verificar que `auth_provider="keycloak"` sigue soportado en `backend/app/config.py` (NO se borra) y que el stack por defecto levanta sin Keycloak

## 14. Estado de entrega y filtros en Notas (Bloque E — governance MEDIO, dominio de negocio)

> Adaptado de la referencia active-ia (`EstadoEntregaEnum`: SUBIDA/PENDIENTE/CORREGIDA/ERROR + `archivado: bool` + filtro `fecha_desde`/`fecha_hasta`), pero mapeado a NUESTRO dominio: la "entrega" es la `ProctoringSessionModel` (examen rendido), y "corregida" en L2.5 significa **veredicto humano registrado** (`decision IS NOT NULL`), nunca corrección automática (regla dura #5). Este estado de entrega es DISTINTO y ortogonal al estado de sync a Moodle (`moodle_writeback_estado.estado`: pendiente/enviado/fallido), que NO se toca.
>
> `estado_entrega` (derivado, NO se persiste — se calcula en la query, evita duplicar fuente de verdad):
> - `no_finalizada`: `finalizada_en IS NULL` (el alumno no entregó/no terminó)
> - `en_revision`: `finalizada_en` seteada, `en_cola_revision` (score ≥ umbral) y `decision IS NULL`
> - `revisada`: `decision IS NOT NULL` (veredicto humano ya registrado — aprobado/anulado/etc.)
> - `finalizada`: `finalizada_en` seteada, sin cola de revisión, sin decision (caso base, no requirió revisión humana)
>
> `archivado` es un flag propio nuevo (bool, default false) en `ProctoringSessionModel` — oculta la fila del listado por default sin borrar nada (soft-hide administrativo, no disciplinario).

- [x] 14.1 Backend: migración Alembic que agrega `archivado: bool NOT NULL DEFAULT false` a `proctoring_session` (branch `activeexam`, patrón de dos pasos si aplica a este tipo de cambio no destructivo — columna con default no lo requiere, agregar directo)
- [x] 14.2 Backend: función pura que deriva `estado_entrega` a partir de `finalizada_en`/`en_cola_revision`/`decision` (mismo patrón que `nivelRiesgo` en frontend `helpers.ts` — lógica centralizada, no duplicada en cada query)
- [x] 14.3 Backend: extender `GET /admin/examenes/{id}/resultados` (`catalog_router.py`) con query params `estado_entrega` (enum arriba), `archivado` (bool, default `false` = solo no archivadas), `fecha_desde`/`fecha_hasta` (sobre `finalizada_en`) — extender `resultados_query.py`, mantener el filtro `estado` (Moodle) existente sin romper compatibilidad
- [x] 14.4 Backend: endpoint `PATCH /admin/examenes/{id}/resultados/{session_id}/archivar` (body `{"archivado": bool}`), protegido por la misma capability que ya protege el panel (tutor de su comisión / coordinador global — mismo scoping de la tarea 8)
- [x] 14.5 Frontend: `ResultadosExamenPanel.tsx` — nuevo select "Estado de entrega" (con las 4 opciones derivadas arriba, labels en español claro, NO términos técnicos), checkbox/toggle "mostrar archivadas", botón archivar/desarchivar por fila
- [x] 14.6 Frontend: date range picker (`fecha_desde`/`fecha_hasta`) reusando el patrón de date picker que ya exista en el repo (revisar `Auditoria.tsx` u otras pantallas con filtro de fecha antes de crear uno nuevo — no duplicar componente)
- [x] 14.7 Tests backend (sin mocks de DB): cada valor de `estado_entrega` se deriva correctamente con datos reales; filtro `archivado=false` excluye archivadas por default; filtro de fecha incluye/excluye por rango; archivar/desarchivar persiste y respeta scoping por comisión (403 fuera de ella)
- [x] 14.8 Tests frontend: selects reflejan las opciones nuevas; combinación de filtros arma el query string esperado; botón archivar dispara el PATCH y refresca la fila

## 15. Evidencia de eventos sin captura — copiar_pegar / cambio_pestana (Bloque F — governance MEDIO, dominio proctoring)

> Discutido y decidido con el dueño (ver engram `pendientes/panel-usuarios-ux`): el screenshot en estos dos eventos NO prueba que el evento ocurrió (a diferencia de `multiples_rostros`/`rostro_ausente`, donde se re-infiere la misma imagen) — es CONTEXTO VISUAL para el revisor humano (L2.5, regla dura #5). Evidencia real nueva: hash (NUNCA contenido, Ley 25.326) de lo pegado en `copiar_pegar`.

- [x] 15.1 Cliente: activar `trigger_evidence: true` para `cambio_pestana` (~línea 295) y `copiar_pegar` (~línea 327) en `frontend/src/proctoring/stateTransitionRules.ts`
- [x] 15.2 Cliente: en el handler de `copiar_pegar`, calcular SHA-256 del contenido pegado (Web Crypto API, `crypto.subtle.digest`) y enviarlo como `payload.clipboard_sha256` — el contenido en sí NUNCA se lee más allá de hashearlo, no se guarda ni se transmite en claro
- [x] 15.3 Backend: `event_service.py` — aceptar y persistir `clipboard_sha256` en el `payload` del evento `copiar_pegar` (ya persiste `sha256_hex` de screenshots; mismo patrón, columna/campo ya JSONB en `payload`, sin migración si el modelo ya es JSONB)
- [x] 15.4 Backend: confirmar que estos dos eventos con evidencia NUEVA siguen SIN sumar automáticamente al veredicto — solo enriquecen el dossier que ve el revisor (regla dura #5, doble red igual que tarea 5.3)
- [x] 15.5 Frontend: mostrar el screenshot de contexto y (si está) el hash de clipboard en el detalle de sesión (`EventoCard.tsx`) con leyenda explícita "contexto, no prueba del evento" — evitar que un revisor lo lea como confirmación automática
- [x] 15.6 Tests: evento `cambio_pestana`/`copiar_pegar` ahora dispara captura; `clipboard_sha256` persiste sin persistir el contenido; score no se ve afectado por la sola presencia de evidencia nueva (mismo patrón que 5.4)

## 16. Eliminar la posibilidad de borrar sesiones de proctoring (Bloque G — compliance, CRÍTICO)

> ⚠️ CRÍTICO (evidencia/cadena de custodia, regla dura de dominio #6/#7). Hallazgo del dueño: hoy existe `DELETE /sessions/{id}` (admin-only) que borra una sesión de proctoring y sus eventos/biometría en CASCADE — contradice directamente la inmutabilidad que c-77 acaba de reforzar con MinIO/Object Lock (evidencia borrable no es evidencia con cadena de custodia). Dos botones en frontend disparan este endpoint: `frontend/src/screens/ProctoringRevisor.tsx` (pantalla "Registro de sesiones", listado) y `frontend/src/screens/ProctoringSessionDetail.tsx` (detalle). El comentario junto al botón del detalle ("Eliminar evidencia — solo admin (cadena de custodia, regla dura #6)") cita la regla que en realidad viola.
>
> Alcance: eliminar el endpoint, el servicio, el método de repositorio y AMBOS botones/handlers de UI — NO dejarlo "oculto" ni detrás de un flag, sacarlo del todo. Si en algún momento hace falta borrar datos por derecho al olvido (DSR, Ley 25.326), eso pasa por el flujo de DSR (`app/domain/dsr/`, `app/application/dsr/service.py`) que ya existe separado — NO por este atajo administrativo. Confirmar que el DSR NO depende de `session_service.eliminar_sesion`/`ProctoringRepository.eliminar_sesion` antes de borrarlos (si depende, extraer la lógica compartida en vez de duplicar).

- [x] 16.1 Confirmar que `session_service.eliminar_sesion` / `ProctoringRepository.eliminar_sesion` no los usa nada del flujo de DSR/retención (`grep` amplio); si los usa, extraer/mantener solo la porción que use el DSR
- [x] 16.2 Eliminar el endpoint `DELETE /sessions/{session_id}` de `backend/app/presentation/api/v1/proctoring/sessions/router.py`
- [x] 16.3 Eliminar `session_service.eliminar_sesion` y `ProctoringRepository.eliminar_sesion` si 16.1 confirma que no los usa nada más
- [x] 16.4 Frontend: quitar el botón "Eliminar sesión" + modal de confirmación + `handleConfirmarBorrado` de `ProctoringSessionDetail.tsx`
- [x] 16.5 Frontend: quitar el botón/flujo de borrado equivalente de `ProctoringRevisor.tsx` (estado `aBorrar`, `handleConfirmarBorrado`, UI asociada)
- [x] 16.6 Quitar `eliminarSesionProctoring` de `frontend/src/lib/apiProctoring/revision.ts` (o donde esté declarada) si queda sin otros usos
- [x] 16.7 Tests: el endpoint ya no existe (405/404, no 204); tests existentes que ejercitaban el borrado se eliminan o se adaptan; suite de `tests/proctoring/` sigue en verde (safety net, comparar contra baseline antes del cambio)

## 17. Registro de sesiones: tabla + paginación + filtros (Bloque H — UX, governance BAJO)

> Decisión del dueño (2026-08-18): "Registro de sesiones" (`frontend/src/screens/ProctoringRevisor.tsx`) hoy son cards agrupadas por examen, SIN filtros. Para un historial que crece sin límite, tabla + filtros escanea mejor que cards (mismo criterio ya aplicado en Notas — tarea 14). Reemplazar el agrupado-por-examen-con-cards por una tabla con paginación real (mismo componente de paginación que ya usa `ResultadosExamenPanel.tsx` — NO inventar uno nuevo) y filtros server-side (NADA hardcodeado en el frontend: las opciones de cada filtro salen de un endpoint/catálogo del backend, mismo patrón que la tarea 14).

- [x] 17.1 Backend: extender `GET /sessions` (o el endpoint que liste sesiones finalizadas) con paginación real (`page`/`page_size`) y filtros: alumno (búsqueda por nombre/legajo/email), examen (`exam_id`/`examen_contenido_id`), rango de fecha (`fecha_desde`/`fecha_hasta` sobre `finalizada_en`), nivel de riesgo (derivado del score — reusar `nivelRiesgo`/la función de riesgo que ya exista en el dominio, NO reinventar el umbral)
- [x] 17.2 Backend: catálogo de opciones de filtro (ej. lista de exámenes con sesiones registradas) servido por un endpoint — el frontend NUNCA hardcodea una lista de exámenes/estados
- [x] 17.3 Frontend: reemplazar el render de cards agrupadas por una tabla (columnas: alumno, examen, fecha, eventos, discrepancias, score/riesgo, acción "ver detalle"), con el mismo componente de paginación de `ResultadosExamenPanel.tsx`
- [x] 17.4 Frontend: filtros de alumno/examen/fecha/riesgo alimentados 100% desde el backend (tarea 17.2), mismo patrón de "Aplicar filtros"/"Limpiar" que Notas
- [x] 17.5 Tests backend (sin mocks de DB): paginación real; cada filtro filtra correctamente con datos reales; catálogo de exámenes refleja solo exámenes con sesiones existentes
- [x] 17.6 Tests frontend: tabla renderiza filas reales; filtros arman el query string esperado; paginación navega correctamente; cero strings de examen/estado hardcodeados en el componente (grep de verificación en el test)

## 18. Fix CRÍTICO: cambio de contraseña propio rechaza `auth_provider='jwt'` (Bloque I — Auth, CRÍTICO)

> ⚠️ CRÍTICO (Auth). Aprobado explícitamente por el dueño (2026-08-18) tras verificación en vivo: `PUT /auth/change-password` (`backend/app/presentation/api/v1/auth/router.py:449`) solo permite `auth_provider in ("local", "lti")` — resabio de la limpieza de Keycloak (migración 0076 renombró el default a `"jwt"`, pero esta lista nunca se actualizó). Confirmado en DB real: el 100% de las cuentas sembradas (incluido admin) tienen `auth_provider="jwt"` y reciben 403 al intentar cambiar su propia contraseña con la clave actual correcta — el self-service de `/admin/perfil` está roto para toda cuenta con ese provider.

- [x] 18.1 Test que falla primero: usuario con `auth_provider="jwt"` + contraseña conocida → `PUT /auth/change-password` con `contrasena_actual` correcta debe devolver 200, NO 403 (contra Postgres real) — `backend/tests/test_c76_18_change_password_jwt_provider.py`, RED confirmado (403) antes del fix
- [x] 18.2 Agregar `"jwt"` a la tupla de providers permitidos en la línea 449 de `router.py`
- [x] 18.3 Segundo caso (triangulación): `auth_provider="keycloak"` (u otro no contemplado) sigue devolviendo 403 — el fix no abre la puerta a cualquier provider, solo a los 3 legítimos (`local`, `lti`, `jwt`) — 2/2 tests verdes
- [x] 18.4 Verificado en vivo (navegador): cambio de contraseña desde `/admin/perfil` funciona con clave actual correcta — admin cambió `Admin123` → `Admin1234`, toast "Contraseña actualizada correctamente."

## 19. Registro de sesiones: fix de layout + materia/comisión + stat cards (Bloque J — UX, governance BAJO)

> Feedback del dueño tras ver la tabla de la tarea 17 en vivo: (1) la card de "Filtros" está ANIDADA dentro de la card "Sesiones finalizadas" — debe ser una card propia, POR ENCIMA, como ya lo hace Notas (`ResultadosExamenPanel.tsx`); (2) la tabla no muestra Materia ni Comisión (el backend YA las resuelve server-side — `SesionResumen.materia_nombre`/`comision_nombre`, campos existentes desde antes, no hace falta tocar el modelo, solo agregar las columnas al render); (3) faltan cards de resumen de estadísticas (cantidad de sesiones finalizadas, eventos totales, distribución de riesgo) — el dueño lo marcó como IMPORTANTE.

- [x] 19.1 Frontend (`ProctoringRevisor.tsx`): sacar el `FiltrosPanel` de adentro de la card de la tabla y ponerlo como card independiente ARRIBA, mismo layout que `ResultadosExamenPanel.tsx` (Filtros arriba → stat cards → tabla+paginación abajo)
- [x] 19.2 Frontend: agregar columnas "Materia" y "Comisión" a la tabla (entre Examen y Fecha), usando `materia_nombre`/`comision_nombre` que YA vienen en cada item de `RegistroSesionesOut.items` — sin tocar el backend para esto
- [x] 19.3 Backend: extender `RegistroSesionesOut` con agregados sobre el TOTAL filtrado (no solo la página actual): `total_eventos`, `total_discrepancias`, y distribución de riesgo (`{bajo, medio, alto}` contando por `nivel_riesgo`, reusar la función de la tarea 17). Estos agregados se calculan sobre el mismo query filtrado, antes de paginar
- [x] 19.4 Frontend: cards de resumen (mismo estilo visual que las stat cards que ya existen en Auditoría/Notas) arriba de la tabla, debajo de Filtros: "Sesiones finalizadas" (= `total`), "Eventos totales", "Discrepancias totales", "Riesgo" (badges bajo/medio/alto con su conteo)
- [x] 19.5 Tests backend: los agregados reflejan el TOTAL filtrado, no la página (ej. con `page_size=5` y 12 resultados totales, `total_eventos` suma los 12, no solo los primeros 5)
- [x] 19.6 Tests frontend: Materia/Comisión se muestran cuando el backend las manda, guion/placeholder claro cuando vienen `null`; stat cards renderizan los agregados del backend, no un cálculo propio sobre `items` (que solo tiene la página actual)
- [x] 19.7 Verificado en vivo (navegador, tras `docker compose up --build`): Filtros como card propia arriba, stat cards (Sesiones/Eventos/Discrepancias/Riesgo bajo-medio-alto) con totales reales, tabla con columnas Materia/Comisión (muestran "—" para la sesión de prueba sin materia vinculada, correcto)

## 20. Registro de sesiones: rework de stats/filtros + sesiones de test eliminables + fix módulo SESIONES muerto (Bloque K)

> Feedback del dueño (2026-08-18) tras ver la tarea 19 en vivo, todo en el mismo bloque para no pisar archivos entre agentes:
>
> 1. **Stat cards**: sacar "Eventos totales" y "Discrepancias totales" (no son decisivas como stat general). Reemplazar por una card "Sobre el umbral de riesgo" (cuenta de sesiones con score ≥ el mismo umbral que usa Cola de revisión — `obtener_umbral_alto`/`umbral_cola_revision`, YA existe, no inventar uno nuevo). Mantener "Sesiones finalizadas" y el desglose Riesgo bajo/medio/alto (ya existen de la tarea 19).
> 2. **Colores de las stat cards**: el estilo actual no sirve. Reusar el patrón visual NEUTRO de stat cards que ya usan `Auditoria.tsx`/`ResultadosExamenPanel.tsx` (ícono + número + label, sin fondos de color fuertes; color solo en los badges chicos de riesgo bajo/medio/alto, mismo esquema `riesgoBadgeTone` que ya se usó en la tarea 19).
> 3. **Orden**: las stat cards van ARRIBA de Filtros (no abajo, como quedó en la tarea 19).
> 4. **Filtros de Materia y Comisión**: faltan — hoy solo hay filtro de Examen. Agregar cascada Materia→Comisión (mismo patrón que Notas: `api.materiasDisponibles()` + `api.comisionesDeMateria()`), ambos alimentando el filtro de sesiones (backend: agregar `materia_id`/`comision_id` como filtros de `GET /sessions/registro`).
> 5. **Por qué hay filas sin Materia/Comisión**: son sesiones `modo='test'` (diagnóstico de cámara/mic, sin examen real vinculado) — comportamiento CORRECTO, no un bug. Pero justamente por ser modo test (NO son evidencia académica real), el dueño pidió que ESAS SÍ se puedan eliminar (a diferencia de las `modo='examen'`, que quedaron protegidas para siempre en la tarea 16 — regla dura #6/#7, cadena de custodia).
> 6. **Encabezado "Sesiones finalizadas"**: sale desproporcionadamente grande comparado con el resto de las páginas con tablas (Notas, Auditoría) y le falta el ícono que esas páginas sí tienen — igualar tamaño/estilo.
> 7. **Módulo "Sesiones" de Auditoría, muerto**: `ModuloAuditoria.SESIONES` existe en el enum/catálogo pero `modulo_de_accion()` (`backend/app/application/audit/acciones.py`) NUNCA lo devuelve — es un filtro que siempre da 0 resultados. Aprovechar este bloque para cerrarlo: la eliminación de sesión de test (punto 5) y el archivado/desarchivado de resultado (gap detectado antes, tarea 14) son candidatos naturales para auditarse bajo `SESIONES`.

- [x] 20.1 Backend: nuevo endpoint `DELETE /sessions/{session_id}` — SOLO permite eliminar si `sesion.modo == 'test'` (409/400 si `modo == 'examen'`, la protección de la tarea 16 se mantiene intacta para evidencia real), admin-only. Auditar con una `AccionAuditoria` nueva (ej. `SESION_TEST_ELIMINADA = "sesion.test.delete"`) bajo `ModuloAuditoria.SESIONES` — agregar el prefijo `"sesion."` a `modulo_de_accion()` para que quede mapeado (cierra el gap del punto 7)
- [x] 20.2 Backend: auditar también `PATCH /{examen_id}/resultados/{session_id}/archivar` (tarea 14, gap detectado sin corregir) — reusar `ModuloAuditoria.SESIONES` con una acción `RESULTADO_ARCHIVAR = "sesion.resultado.archivar"` (mismo prefijo `sesion.`, cae en el mismo mapeo del punto anterior)
- [x] 20.3 Backend: filtros `materia_id`/`comision_id` en `GET /sessions/registro` (vía `examen_contenido_id` → comisión → materia, mismo join que ya resuelve `materia_nombre`/`comision_nombre`)
- [x] 20.4 Backend: agregado `en_cola_revision: int` en `RegistroSesionesOut` (cuenta sobre el TOTAL filtrado, mismo patrón que `riesgo_bajo/medio/alto` de la tarea 19) — sacar `total_eventos`/`total_discrepancias` de la respuesta si ya no los consume nadie más (verificar antes de borrar)
- [x] 20.5 Frontend: reordenar `ProctoringRevisor.tsx` — stat cards ARRIBA, Filtros abajo (swap del orden de la tarea 19)
- [x] 20.6 Frontend: reemplazar cards de Eventos/Discrepancias por "Sobre el umbral de riesgo"; restyling neutro (mismo patrón visual que `Auditoria.tsx`/`ResultadosExamenPanel.tsx`, sin fondos de color fuertes)
- [x] 20.7 Frontend: filtros Materia→Comisión en cascada (mismo patrón de `Notas.tsx`), integrados con el filtro de Examen existente
- [x] 20.8 Frontend: botón "Eliminar" por fila SOLO quando `modo === 'test'` (nunca para `modo === 'examen'`), con modal de confirmación (mismo componente `ConfirmModal` que se usaba antes de la tarea 16)
- [x] 20.9 Frontend: igualar tamaño de encabezado "Sesiones finalizadas" + agregar ícono, mismo estilo que el resto de las páginas con tabla
- [x] 20.10 Tests backend: eliminar sesión modo=test → 204 + fila desaparece + queda en audit_log bajo SESIONES; eliminar sesión modo=examen → rechazada (409/400), NO se borra; filtros materia/comisión filtran correctamente; `en_cola_revision` refleja el total filtrado no la página; archivar resultado queda auditado
- [x] 20.11 Tests frontend: botón eliminar ausente en filas modo=examen; presente y funcional en modo=test; filtros materia/comisión arman el query string esperado
- [x] 20.12 Verificado en vivo (navegador, tras `docker compose up --build`): stat cards arriba (neutras, con íconos "groups"/"gavel"), Filtros abajo con cascada Materia→Comisión funcionando, eliminé la sesión modo=test real (modal de confirmación claro, tabla quedó en 0, stats se refrescaron), y confirmé en Auditoría que quedó registrada bajo el módulo "Sesiones" (antes muerto) con descripción legible "Eliminó la sesión de diagnóstico {id}" — PENDIENTE: requiere `docker compose -f infra/docker-compose/docker-compose.dev.yml up -d --build backend` (el dueño lo corre, no este agente) y luego verificación manual en el navegador

## 13. Actualización de specs y cierre

- [x] 13.1 Verificar `openspec validate --specs --strict` para los deltas de este change — `openspec validate c-76-panel-supervision-en-vivo --strict` → "Change is valid". Los 3 specs que fallan en `openspec validate --specs --strict` a nivel repo (post-exam-reports, report-exports-and-summary, statistical-distribution-analytics) son preexistentes y ajenos a este change.
- [x] 13.2 Actualizar `CHANGES.md` con la entrada de c-76 (no lo hace el archive automáticamente)
- [x] 13.3 Resolver o dejar registradas las Open Questions del design (Q1–Q7) antes de archivar — ver actualización en `design.md` §Open Questions
