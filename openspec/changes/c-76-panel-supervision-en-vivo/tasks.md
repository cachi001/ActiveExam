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

## 13. Actualización de specs y cierre

- [x] 13.1 Verificar `openspec validate --specs --strict` para los deltas de este change — `openspec validate c-76-panel-supervision-en-vivo --strict` → "Change is valid". Los 3 specs que fallan en `openspec validate --specs --strict` a nivel repo (post-exam-reports, report-exports-and-summary, statistical-distribution-analytics) son preexistentes y ajenos a este change.
- [x] 13.2 Actualizar `CHANGES.md` con la entrada de c-76 (no lo hace el archive automáticamente)
- [x] 13.3 Resolver o dejar registradas las Open Questions del design (Q1–Q7) antes de archivar — ver actualización en `design.md` §Open Questions
