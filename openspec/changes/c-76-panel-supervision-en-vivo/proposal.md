## Why

El panel de supervisión funcional (REST/polling slim entregado por C-15) hoy está atado a un rol `proctor` que en la práctica no existe como puesto institucional: quien supervisa en vivo es el **tutor** (docente de la comisión) y quien decide el veredicto es el **coordinador**. Mantener `proctor` como rol separado duplica autoridad, confunde la UX y contradice el modelo de C-73 (pertenencia por comisión). Este change **elimina el rol PROCTOR**, reasigna la supervisión en vivo al TUTOR acotada a sus comisiones, consolida el veredicto en COORDINADOR/REVISOR, y rediseña la UX del panel de detalle de sesión y de dos flujos administrativos (alta de usuario con clave temporal y subida de nota) que hoy tienen usabilidad pobre.

No es tiempo real de producción: eso lo aporta **c-15b** (transporte SSE, bloqueado por C-03) más adelante. c-76 trabaja sobre el panel funcional slim ya existente y **no depende de C-03**.

## What Changes

**Bloque A — Rediseño de roles y supervisión en vivo:**

- **BREAKING**: Se **elimina el rol `PROCTOR`** del enum `Rol` (`backend/app/domain/auth/roles.py`) y de todas las listas/mapas que lo referencian (`ROLES_CON_MFA`, capability `supervisar_vivo`). No se fusiona ni renombra: se saca directamente. `COORDINADOR` (que ya tiene `revisar_sesion` = veredicto) absorbe la supervisión global.
- **BREAKING**: `TUTOR` gana la capacidad `supervisar_vivo` **acotada por comisión** (solo las comisiones donde está asignado como docente, reusando `asignar_docente` de C-73 §9) y el acceso al **registro/historial** de esas sesiones. El tutor **NUNCA** da veredicto (exclusivo de `COORDINADOR` y `REVISOR`).
- El **chat y las pausas** pasan de `proctor↔alumno` a **`tutor↔alumno`**. El alumno **no puede iniciar** el chat; solo responde cuando el tutor le escribe.
- Las **pausas las aprueba el tutor**, con un **límite configurable** de pausas por sesión desde Configuración del Sistema (**default 2**). Hoy `chat_pausa_service.py` no limita la cantidad, solo el timeout de 120s del pedido.
- Durante una pausa aprobada se **registran capturas (screenshots)** del alumno, para verificar ausencia real y no confiar solo en el estado "pausa aprobada" (regla dura #6: cliente = sensor no confiable).
- **Rediseño visual** de la página de detalle de sesión (`ProctoringSessionDetail.tsx` / `SessionDetail.tsx`) para ambos estados (con/sin riesgo), consumida por tutor (sin botón de veredicto) y coordinador (con veredicto).

**Bloque B — UX administrativa (primeras tareas implementables):**

- **Alta de usuario con clave temporal — página dedicada + modal** (PRIMERA tarea). El backend ya devuelve `password_generada` en `POST /users`; hoy el frontend la muestra en un toast efímero (`GestionUsuarios.tsx:165`), que se pierde. Se agrega ruta nueva `/admin/usuarios/nuevo` con formulario dedicado y **modal post-creación** que muestra la clave con botón "copiar" (clipboard), aviso "guardala, no la vas a volver a ver" y "el usuario deberá cambiarla en el primer ingreso".
- **UX de subir nota**: botón más claro (hoy dice "sincronizar con Moodle"), **subida individual** de nota, y **selección de filas** (checkbox) para subir en lote.
- **Columna de acción sticky**: la columna de acciones (final de la tabla) queda **fija** al hacer scroll horizontal, siempre visible.

**Bloque C — Endurecimiento backend (governance BAJO):**

- **Validación backend `nota_aprobacion ≤ nota_maxima`**: hoy la invariante se aplica de forma imperativa en los routers de examen (`nota_aprobacion > nota_maxima → 422` en creación desde banco y en PATCH de config) y en el frontend, pero **no está declarada en el schema Pydantic**. Se agrega la validación cruzada **al nivel del schema** (`CrearDesdebancoRequest`, `ActualizarConfigRequest`), con `extra='forbid'`, como defensa en profundidad para que ningún endpoint nuevo omita el chequeo. La validación de dominio existente (`validar_config_examen`) se conserva.

**Bloque D — Limpieza de deploy (governance MEDIO):**

- **Deploy cleanup — sacar Keycloak**: el auth real del proyecto es el **JWT propio** (`own_issuer` / provider `jwt`, C-55) + login local. Keycloak quedó en los archivos de deploy pero **no se usa** como pieza operativa. Se limpian de la infra las piezas atadas exclusivamente a Keycloak que no estén en uso: servicio `keycloak` en `infra/docker-compose/docker-compose.yml` (+ su `depends_on` en `api`, envs `KEYCLOAK_*`/`KC_*`, puerto 8080), artefactos bajo `infra/keycloak/` (`Dockerfile`, `proctoring-realm.json`, `railway.json`), placeholders `KEYCLOAK_*` en las plantillas `.env`. ⚠️ Es limpieza de **config**, no toca dominio: el código que soporta `auth_provider="keycloak"` como modo alternativo (settings `keycloak_*` en `app/config.py`) **NO se toca** — es la abstracción de proveedor de C-55, no una pieza muerta. El relevamiento de qué está realmente sin uso es el **primer paso** antes de borrar; ante duda, queda como Open Question.

## Capabilities

### New Capabilities
- `alta-usuario-clave-temporal`: Página dedicada de alta de usuario y modal post-creación que presenta la contraseña temporal generada por el backend de forma persistente, copiable y con los avisos de un solo uso / cambio obligatorio en el primer ingreso.
- `subida-nota-individual-lote`: Subida de nota individual por fila y en lote con selección múltiple (checkbox), con etiqueta de acción clara.
- `tabla-accion-sticky`: Columna de acciones fija (sticky) al final de una tabla, siempre visible durante scroll horizontal.
- `pausa-limite-configurable`: Límite configurable de pausas por sesión (default 2), definido en Configuración del Sistema y aplicado al aprobar pausas.
- `pausa-screenshot-capture`: Captura de screenshots del alumno durante una ventana de pausa aprobada, como evidencia de ausencia real.
- `validacion-nota-examen`: Validación declarativa a nivel de schema Pydantic de la invariante `nota_aprobacion ≤ nota_maxima` (defensa en profundidad sobre la validación imperativa ya existente en routers y dominio).
- `deploy-config`: La configuración de deploy refleja que el auth es JWT propio; Keycloak se remueve de las piezas de deploy no usadas (se conserva el modo alternativo `auth_provider="keycloak"` en el código).

### Modified Capabilities
- `contextual-rbac`: Se elimina el rol `proctor` del enum de roles y de las políticas MFA; el conjunto de roles válidos cambia (BREAKING).
- `supervision-vivo-diferenciada`: `supervisar_vivo` deja de incluir `proctor`; pasa a `tutor` (acotado por comisión), `revisor`, `coordinador`, `admin_sistema`.
- `proctor-contextual-access`: El acceso al panel deja de estar gobernado por el rol `proctor`; pasa a tutor (acotado por comisión) + coordinador/admin. Rename conceptual proctor→tutor/coordinador.
- `proctor-session-actions`: El chat pasa a `tutor↔alumno` (el alumno no inicia); el tutor registra observaciones y puede forzar cierre pero NO emite veredicto (exclusivo coordinador/revisor).
- `proctor-pausa-autorizada`: La pausa la solicita el alumno y la **aprueba el tutor** (antes proctor); se agrega límite configurable por sesión y captura de screenshots durante la pausa.

## Impact

- **Auth/RBAC (CRÍTICO)**: `backend/app/domain/auth/roles.py` (enum `Rol`, `ROLES_CON_MFA`), `backend/app/domain/auth/capabilities.py` (`CAPABILITY_ROLES["supervisar_vivo"]`). Migración de datos: usuarios y asignaciones de rol `proctor` existentes en la DB (Keycloak/JWT propio) deben remapearse a `coordinador` o `tutor` según su función real, o rechazarse; los JWT con claim `proctor` dejan de mapear a un rol de dominio (`parse_rol` los descarta silenciosamente — hoy tolerante, ver Open Questions).
- **Backend proctoring**: `backend/app/application/proctoring/chat_pausa_service.py` (límite de pausas, actor tutor, screenshots), routers de chat/pausa, config del sistema (nuevo umbral de pausas), captura de screenshot durante pausa.
- **Backend users**: `backend/app/presentation/api/v1/users/router.py` (`POST /users` ya devuelve `password_generada`, sin cambios de contrato).
- **Frontend**: nueva ruta `/admin/usuarios/nuevo` (página + modal), `GestionUsuarios.tsx` (quitar toast efímero), `ProctoringSessionDetail.tsx` / `SessionDetail.tsx` (rediseño), tabla de notas (botón, individual, checkbox lote, columna sticky), panel de supervisión en vivo (`Proctor.tsx`) con acotado por comisión para tutor.
- **Specs**: 3 specs con nombre `proctor-*` requieren rename conceptual (no se renombra el archivo en este change salvo que el skill de specs lo decida; el contenido se actualiza vía delta).
- **Validación de nota (BAJO)**: `backend/app/presentation/api/v1/exam_content/schemas.py` (`CrearDesdebancoRequest`, `ActualizarConfigRequest`): validador cruzado a nivel schema. No cambia el contrato HTTP (mismo 422); no toca `validar_config_examen` (dominio, se conserva).
- **Deploy/infra (MEDIO)**: `infra/docker-compose/docker-compose.yml` (servicio `keycloak`, `depends_on` en `api`, envs `KEYCLOAK_*`/`KC_*`, puerto 8080), `infra/keycloak/` (`Dockerfile`, `proctoring-realm.json`, `railway.json`), plantillas `.env` (placeholders `KEYCLOAK_*`). **NO impacta** `backend/app/config.py` (settings `keycloak_*` = modo alternativo de C-55, se conservan).
- **NO impacta**: C-03 (no hay dependencia). c-15b aportará el transporte SSE en tiempo real después, sobre este panel rediseñado.
