## Context

**Estado actual**: La KB (`03_actores_y_roles.md`, `05_reglas_de_negocio.md`) y el spec `contextual-rbac` (C-06) documentan que el proctor está scoped a sus asignaciones. El código de dominio (`authorization.py::autorizar_proctor_sobre_examen`) y el servicio de aplicación (`ContextualAuthorizationService.autorizar_proctor`) implementan esa restricción. Sin embargo, el `ContextualAuthorizationService` está **huérfano**: ningún router lo cablea hoy, por lo que el scoping **no se enforcea en runtime**. El impacto del cambio es principalmente documental y de coherencia de dominio.

**Requerimiento del dueño**: el Proctor tiene visión global de exámenes — puede supervisar cualquier examen activo sin necesitar asignación previa. El Revisor académico **sigue scoped a su jurisdicción** (sin cambios). El gate de acceso a evidencia (MFA + propósito en audit log) tampoco cambia.

**Relación con C-01**: este cambio relaja el principio de mínimo privilegio para el proctor. Esa relajación debe quedar justificada y registrada en el DPIA (C-01). Este change crea la dependencia explícita: C-01 debe absorber la justificación antes de que el sistema se considere gobernanza-completo.

**Relación con C-06**: C-06 ya está Complete. Este change genera un **delta spec** que modifica la capability `contextual-rbac` de C-06 sin tocar los demás specs de C-06 (jwt-validation, mfa-enforcement, realtime-handshake-auth, keycloak-federation-jit).

## Goals / Non-Goals

**Goals:**
- Actualizar RN-AU-07 en `05_reglas_de_negocio.md` para reflejar el alcance global del proctor.
- Actualizar la fila del Proctor y el párrafo del RBAC en `03_actores_y_roles.md`.
- Generar un delta spec que MODIFIQUE los scenarios del proctor en `contextual-rbac` (C-06): eliminar el scoping a asignaciones, añadir el scenario de alcance global.
- Simplificar `autorizar_proctor_sobre_examen` en el dominio: el proctor con rol válido y MFA satisfecho pasa siempre.
- Simplificar `ContextualAuthorizationService`: el método `autorizar_proctor` ya no resuelve asignaciones.
- Actualizar los tests de aislamiento del proctor: los casos "examen no asignado → ForbiddenError" se eliminan; se añade "proctor global con MFA → siempre autorizado".
- Dejar traza explícita de la relajación del mínimo privilegio como dependencia de gobernanza con C-01.

**Non-Goals:**
- NO cambiar el scoping del revisor (jurisdicción) ni el gate de acceso a evidencia.
- NO cablear el `ContextualAuthorizationService` en routers (eso está fuera del alcance de C-06 y de este change — el servicio está huérfano de forma intencional hasta el change de paneles/revisión).
- NO modificar la infraestructura de Keycloak, el MFA enforcement, ni el handshake WS/SSE.
- NO implementar una entidad "Asignación de examen al proctor" (no existe ni existe razón para crearla ahora).
- NO tocar specs de otras capabilities de C-06 (jwt-validation, mfa-enforcement, realtime-handshake-auth, keycloak-federation-jit).

## Decisions

### D1 — Proctor global: eliminar el parámetro `examenes_asignados` de la función de dominio
**Decisión**: `autorizar_proctor_sobre_examen` deja de recibir `examenes_asignados`. La nueva lógica: si el principal tiene rol `PROCTOR` y MFA satisfecho (o es admin), el acceso se concede sin restricción adicional. El nombre de la función puede mantenerse para no romper referencias, o renombrarse a `autorizar_proctor` para mayor claridad — se opta por renombrar para que el nombre refleje la semántica real.
**Por qué**: el parámetro `examenes_asignados` solo tiene sentido con scoping; mantenerlo vacío o ignorado crearía confusión técnica y deuda de documentación.
**Alternativa considerada**: mantener el parámetro como opcional/ignorado — genera confusión sobre si aún se usa; descartada.

### D2 — `ContextualAuthorizationService.autorizar_proctor` se simplifica (no se elimina)
**Decisión**: el método se simplifica — ya no llama a `_examenes_asignados` ni resuelve el repositorio de asignaciones. Solo delega a `authorization.autorizar_proctor(principal)`. El servicio sigue existiendo porque `autorizar_revisor` y `acceder_a_evidencia` siguen siendo necesarios.
**Por qué**: el servicio es el punto de entrada de la capa de aplicación; eliminarlo forzaría a reescribir la firma de los futuros consumidores. Simplificarlo es suficiente.
**Alternativa considerada**: eliminar el servicio entero — no viable porque `autorizar_revisor` y `acceder_a_evidencia` siguen necesitando repositorios.

### D3 — Delta spec MODIFICA, no REEMPLAZA, `contextual-rbac`
**Decisión**: el delta spec declara los scenarios del proctor bajo `## MODIFIED Requirements` y `## REMOVED Requirements` con su contenido completo, para que el archive de C-50 produzca un spec mergeado coherente. Los scenarios del revisor y del gate de evidencia quedan intocados en el delta (no se listan).
**Por qué**: el esquema spec-driven de OpenSpec requiere que MODIFIED incluya el bloque completo actualizado; una lista parcial pierde detalle en el archive.
**Alternativa considerada**: nuevo spec separado para el proctor global — fragmentaría la capability en dos specs, haciéndola difícil de navegar.

### D4 — Nota de DPIA como dependencia explícita (no bloqueante para el apply)
**Decisión**: el design registra la relajación del mínimo privilegio como una dependencia de gobernanza con C-01. Esto no bloquea el apply de C-50 (el código/docs se pueden actualizar), pero C-50 no se considera gobernanza-completo hasta que C-01 absorba la justificación.
**Por qué**: la Ley 25.326 y el DPIA exigen que cualquier decisión que amplíe el acceso a datos personales quede justificada. Un proctor que ve TODOS los exámenes accede potencialmente a más datos biométricos y de comportamiento.
**Alternativa considerada**: bloquear C-50 hasta que C-01 esté completo — innecesario; C-01 es 0/23 y bloquearlo retrasaría un cambio de coherencia que es de bajo riesgo en runtime.

## Risks / Trade-offs

- **[Relajación del mínimo privilegio: proctor con visión global]** → Mitigación: D4 — registrar justificación en DPIA (C-01); el MFA obligatorio para proctor sigue vigente; el acceso a evidencia sigue requiriendo propósito declarado en audit log.
- **[Función renombrada rompe referencias futuras]** → Mitigación: el servicio está huérfano actualmente; no hay consumidores en producción que llamen `autorizar_proctor_sobre_examen` vía el servicio. Renombrar ahora es seguro.
- **[Tests eliminados sin reemplazo funcional]** → Mitigación: los tests de "proctor global → siempre autorizado" reemplazan directamente los de scoping; se mantiene cobertura del MFA enforcement del proctor.
- **[Coherencia KB vs. código]** → Este change alinea ambos; el riesgo es no hacerlo (divergencia silenciosa que confunde a futuros agentes).

## Migration Plan

1. Actualizar KB: `03_actores_y_roles.md` (fila Proctor, párrafo RBAC) y `05_reglas_de_negocio.md` (RN-AU-07).
2. Crear delta spec en `specs/contextual-rbac/spec.md` con MODIFIED/REMOVED del proctor.
3. Actualizar `backend/app/domain/auth/authorization.py`: simplificar / renombrar `autorizar_proctor_sobre_examen`.
4. Actualizar `backend/app/application/auth/authorization_service.py`: simplificar `autorizar_proctor` del servicio.
5. Actualizar tests: `test_auth_rbac_contextual.py` y `test_auth_contextual_service.py`.
6. Verificar que todos los tests pasen sin mocks de DB.

**Rollback**: revertir los 5 archivos modificados. No hay migraciones de DB ni cambios de infraestructura.

## Open Questions

- ¿El proctor global necesita algún atributo adicional en el JWT/Keycloak para indicar que tiene visión global, o basta con el rol `PROCTOR`? → Por ahora basta con el rol; si surge la necesidad de un proctor "restringido a un campus" en el futuro, se modela como un sub-rol o atributo nuevo (decisión diferida).
- ¿La simplificación de `autorizar_proctor` en el servicio implica que el método puede volverse síncrono (sin `async`)? → Sí, ya que no llama al repositorio de asignaciones. Se puede simplificar a síncrono; no hay impacto externo dado que el servicio está huérfano.
