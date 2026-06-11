## 1. Actualizar Knowledge Base

- [x] 1.1 En `knowledge-base/05_reglas_de_negocio.md`, actualizar RN-AU-07: reemplazar "un proctor observa solo exámenes asignados; un revisor solo su jurisdicción" por "el proctor observa todos los exámenes activos (alcance global); el revisor solo su jurisdicción"
- [x] 1.2 En `knowledge-base/03_actores_y_roles.md`, actualizar la fila del Proctor en la tabla RBAC: columna Restricciones pasa de "Solo exámenes asignados; MFA" a "Todos los exámenes activos (alcance global); MFA"
- [x] 1.3 En `knowledge-base/03_actores_y_roles.md`, actualizar el párrafo introductorio del RBAC: reemplazar "un proctor observa exámenes específicos asignados" por "el proctor observa todos los exámenes activos"

## 2. Dominio — authorization.py

- [x] 2.1 En `backend/app/domain/auth/authorization.py`, renombrar la función `autorizar_proctor_sobre_examen` a `autorizar_proctor` y eliminar el parámetro `examenes_asignados`
- [x] 2.2 Reescribir el cuerpo de `autorizar_proctor`: si el principal tiene rol `ADMIN_EXAMENES` o `ADMIN_SISTEMA`, retornar. Si tiene rol `PROCTOR`, llamar a `verificar_mfa(principal)` y retornar (acceso global). Si no tiene ninguno de los dos, levantar `ForbiddenError`
- [x] 2.3 Actualizar el docstring de la función para reflejar el alcance global del proctor (eliminar la referencia a `Asignacion` y `examenes_asignados`)

## 3. Aplicación — authorization_service.py

- [x] 3.1 En `backend/app/application/auth/authorization_service.py`, eliminar el método privado `_examenes_asignados` del `ContextualAuthorizationService`
- [x] 3.2 Actualizar el método `autorizar_proctor` del servicio: eliminar la resolución del repositorio de asignaciones; simplificar la firma a `def autorizar_proctor(self, principal, *, exam_id: str) -> None` (síncrono, sin `async`) y delegar directamente a `authorization.autorizar_proctor(principal)`
- [x] 3.3 Actualizar el docstring del método para reflejar alcance global; eliminar la referencia a `Asignacion` y `AssignmentRepository`
- [x] 3.4 Verificar que el import de `AssignmentRepository` sigue siendo necesario (lo usa `autorizar_revisor` indirectamente a través del constructor); si ya no se usa, eliminarlo del import

## 4. Tests — actualización

- [x] 4.1 En `backend/tests/test_auth_rbac_contextual.py`, eliminar los tests `test_proctor_sobre_examen_no_asignado_rechazado` y `test_proctor_sobre_examen_asignado_autorizado`
- [x] 4.2 En `backend/tests/test_auth_rbac_contextual.py`, añadir test `test_proctor_global_autorizado_sin_asignacion`: proctor con MFA satisfecho sobre cualquier exam_id → no levanta excepción (llama a `authorization.autorizar_proctor`)
- [x] 4.3 En `backend/tests/test_auth_rbac_contextual.py`, añadir test `test_proctor_sin_mfa_rechazado`: proctor sin MFA satisfecho → `MfaRequiredError`
- [x] 4.4 En `backend/tests/test_auth_rbac_contextual.py`, verificar que `test_admin_examenes_no_limitado_por_asignacion` sigue pasando tras el renombrado (actualizar la llamada a `autorizar_proctor` con la nueva firma)
- [x] 4.5 En `backend/tests/test_auth_contextual_service.py`, eliminar los tests `test_proctor_no_asignado_rechazado_por_servicio` y `test_proctor_asignado_autorizado_por_servicio`
- [x] 4.6 En `backend/tests/test_auth_contextual_service.py`, añadir test `test_proctor_global_autorizado_por_servicio`: proctor con MFA → servicio no levanta excepción, sin necesidad de repositorio de asignaciones con datos
- [x] 4.7 Correr los tests de auth con DB real / repositorios en memoria (sin mocks de DB) y confirmar que todos pasan: `pytest backend/tests/test_auth_rbac_contextual.py backend/tests/test_auth_contextual_service.py -v`

## 5. Nota de gobernanza — DPIA

- [x] 5.1 En `design.md` (ya redactado en D4), verificar que queda explícita la nota: "La relajación del mínimo privilegio para el proctor debe quedar justificada en el DPIA (C-01, hoy 0/23). C-50 no se considera gobernanza-completo hasta que C-01 absorba esa justificación"
- [x] 5.2 Añadir una nota breve en `knowledge-base/10_preguntas_abiertas.md` (sección de preguntas abiertas o cambios relevantes) indicando que C-50 revierte RN-AU-07 y que C-01 debe registrar la justificación de la relajación del mínimo privilegio para el proctor global
