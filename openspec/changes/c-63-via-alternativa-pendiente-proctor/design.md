## Context

El flujo de vía alternativa (RN-CO-05) existe para proteger el derecho del alumno a no entregar datos biométricos (Ley 25.326). El backend ya tiene el endpoint `POST /api/v1/consent/alternative` que registra la elección en el audit log y encola la escalación (C-08), pero:

1. El audit log es append-only e inmutable: no puede almacenar estado mutable (`pendiente` → `habilitado`).
2. El frontend ignora la respuesta del endpoint y navega directo a `/sala-espera` con un toast falso.
3. El gate `recalcularPerfilCompleto` en `api.ts:165` cortocircuita con `via_alternativa === true`, marcando biometría como vigente sin verificación humana.
4. No existe mecanismo para que un proctor vea solicitudes pendientes ni las habilite.

Constraints del módulo slim (Railway): postgres:16-alpine (sin TimescaleDB), sin Keycloak (auth JWT propia), sin MinIO. Los tests se escriben contra `app.main_slim` / `SlimSettings`.

## Goals / Non-Goals

**Goals:**
- Persistir el estado mutable de la solicitud de vía alternativa en una tabla propia (`solicitudes_via_alternativa`).
- Bloquear el gate de rendir mientras el estado sea `pendiente_proctor`.
- Proveer endpoints mínimos para que un proctor/admin habilite solicitudes (`POST /alternative/{user_id}/habilitar`) y las liste (`GET /alternative/pendientes`).
- Corregir el frontend: sin bypass en `api.ts:165`, sin navegación automática a `/sala-espera`, pantalla de espera real.
- No romper el flujo normal (acuse afirmativo + biometría).
- No implementar la cola de revisión completa de c-16/c-47/c-48.

**Non-Goals:**
- Rechazo de solicitudes de vía alternativa (queda fuera — solo habilitar o mantener pendiente).
- Notificaciones push/email al proctor (fuera del alcance; el proctor consulta manualmente el listado).
- UI de panel de proctor completo (solo el endpoint mínimo; la UI del panel proctor pertenece a c-16).
- Caducidad automática de solicitudes pendientes.

## Decisions

### D-01: Nueva tabla `solicitudes_via_alternativa` para el estado mutable

**Decisión**: crear tabla `solicitudes_via_alternativa` (columnas: `id`, `user_id`, `exam_id`, `estado` ENUM, `timestamp_solicitud`, `timestamp_habilitacion` NULLABLE, `habilitado_por` NULLABLE) con migración Alembic.

**Alternativa rechazada — extender el audit log**: el audit log es append-only e inmutable por diseño (DD-13, trazabilidad legal). Convertirlo en estado mutable rompe su semántica y la garantía de no-repudio.

**Alternativa rechazada — columna en la tabla de enrollment**: la tabla de enrollment no existe todavía en el módulo slim (es mock en el frontend); añadir una columna ad-hoc acoplaría la vía alternativa a una entidad que pertenece a otro dominio.

**Rationale**: la solicitud de vía alternativa es una entidad de ciclo de vida propio (nace como pendiente, transiciona a habilitada). Una tabla propia expresa esa semántica correctamente y es migrable sin tocar inmutables.

### D-02: Estado ENUM `EstadoViaAlternativa` con dos valores iniciales

**Decisión**: `pendiente_proctor` y `habilitado_por_proctor`. No se agrega `rechazado` en este change (Non-Goal).

**Rationale**: limitar el scope al mínimo necesario. Agregar `rechazado` implica decidir el flujo de notificación al alumno — eso es trabajo de c-47. El ENUM en la BD permite agregar el valor sin riesgo en un change posterior.

### D-03: `ResolucionConsentimiento` extiende con dos nuevos valores

**Decisión**: agregar `VIA_ALTERNATIVA_PENDIENTE` y `VIA_ALTERNATIVA_HABILITADA` al enum de `rules.py`. `evaluar_gate` levanta `ConsentNotResolvedError` para `PENDIENTE` (gate cerrado) y retorna `True` para `HABILITADA`. El valor existente `VIA_ALTERNATIVA` se depreca hacia `HABILITADA` (retrocompatibilidad: si hay registro en audit log sin solicitud, se trata como habilitado para no romper datos existentes).

**Alternativa rechazada — gate separado "alternative_gate"**: añadir complejidad de superficie sin beneficio; el gate existente ya tiene la extensión natural.

### D-04: Frontend — eliminar bypass y añadir estado `via_alternativa_pendiente`

**Decisión**: en `api.ts`, eliminar la línea `e.consentimiento?.via_alternativa === true ||` de `recalcularPerfilCompleto`. El método `puedeRendir` reconoce el nuevo código de retorno `via_alternativa_pendiente` (bloquea con mensaje claro) y `via_alternativa_habilitada` (permite rendir sin biometría). Se añade `solicitarViaAlternativa(examId)` que llama al endpoint real y retorna el estado.

**Rationale**: el bypass es el origen del bug de seguridad. La separación de códigos (`pendiente` vs `habilitado`) permite diferenciar el mensaje al alumno sin lógica if/else ad-hoc.

### D-05: `Consent.tsx` y `EnrollmentConsentStep.tsx` — pantalla de espera

**Decisión**: al elegir vía alternativa, ambas pantallas llaman `api.solicitarViaAlternativa(examId)`, muestran un card informativo "Tu solicitud quedó registrada. Un proctor verificará tu identidad." y NO navegan a `/sala-espera`. El botón Rendir en Mis Exámenes queda deshabilitado con el motivo `via_alternativa_pendiente`.

**Alternativa rechazada — nueva ruta `/alternativa-pendiente`**: innecesario; el card informativo inline cumple el propósito sin añadir rutas.

### D-06: Endpoint de habilitación mínima (proctor/admin)

**Decisión**:
- `POST /api/v1/consent/alternative/{user_id}/habilitar` — body: `{ exam_id }`, auth: rol `proctor` o `admin`. Transiciona `pendiente_proctor` → `habilitado_por_proctor`, registra `habilitado_por` y `timestamp_habilitacion`.
- `GET /api/v1/consent/alternative/pendientes` — lista solicitudes con estado `pendiente_proctor`. Auth: proctor/admin.

**Alternativa rechazada — reutilizar `/alternative` existente con un campo `action`**: el endpoint existente es el del alumno (POST sin auth proctor). Mezclar acciones de alumno y proctor en el mismo path viola el principio de responsabilidad única y complica los permisos.

### D-07: Migración Alembic en dos pasos (slim)

**Decisión**: migración nueva que crea la tabla `solicitudes_via_alternativa` con el ENUM de estados. No destructiva, no toca tablas existentes. Compatible con postgres:16-alpine.

### D-08: Tests contra módulo slim

**Decisión**: todos los tests de este change se escriben contra `app.main_slim` / `SlimSettings`. Tests de: persistencia del estado (repository), gate (rules puro, sin DB), endpoints REST (TestClient + postgres real via pytest-docker o contenedor levantado por fixture).

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| Retrocompatibilidad: alumnos existentes con `VIA_ALTERNATIVA` en audit log pero sin registro en la tabla nueva quedan `NO_RESUELTO` | D-03: si hay entrada en audit log sin solicitud en la tabla, `resolve()` retorna `VIA_ALTERNATIVA_HABILITADA` para no bloquear a nadie retroactivamente |
| El proctor podría nunca habilitar (solicitud "huérfana") | Alcance de este change: la solicitud queda bloqueada hasta acción humana. El SLA de habilitación es decisión operativa fuera del scope técnico |
| El endpoint de habilitación expone `user_id` en el path | user_id en el módulo slim es el `id_institucional` (opaco, no personal). Si se cambia a UUID interno en el futuro, el cambio es en la auth dependency |
| La migración añade tabla nueva: riesgo de fallo en Railway | Migración no destructiva (solo CREATE TABLE + CREATE TYPE). Rollback = DROP TABLE si no hay datos |

## Open Questions

- ¿El `exam_id` es opcional en la solicitud de vía alternativa del perfil (EnrollmentConsentStep)? El enrollment de perfil no tiene un examen asociado. **Supuesto tomado**: `exam_id = "perfil"` como valor sentinel para la solicitud de enrollment; el gate por-examen usa el `exam_id` real.
- ¿La lista de pendientes necesita paginación desde el día uno? **Supuesto tomado**: sin paginación — se implementa cuando c-16 monta el panel de proctor completo.
