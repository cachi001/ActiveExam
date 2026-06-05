## Why

El dueño del proyecto decidió que el **Proctor tiene alcance GLOBAL**: puede observar cualquier examen activo, independientemente de asignaciones. La KB (`03`, `05`) y el spec `contextual-rbac` (C-06) documentan hoy que el proctor está scoped a sus asignaciones — esa restricción es incoherente con el requerimiento real y debe revertirse en toda la documentación, specs y código de dominio.

El `ContextualAuthorizationService.autorizar_proctor` está actualmente **huérfano** (no cableado en ningún router), por lo que el cambio es de bajo riesgo en runtime, pero alto impacto en coherencia documental y de dominio.

## What Changes

- **KB `03_actores_y_roles.md`**: fila Proctor pasa de "Solo exámenes asignados" a "Todos los exámenes activos (alcance global)"; párrafo introductorio del RBAC actualizado.
- **KB `05_reglas_de_negocio.md`**: **RN-AU-07** pasa de "un proctor observa solo exámenes asignados; un revisor solo su jurisdicción" a "el proctor observa todos los exámenes activos (alcance global); el revisor solo su jurisdicción".
- **Delta spec sobre `contextual-rbac` (C-06)**: MODIFICA los escenarios del proctor — elimina el scenario "Proctor accede solo a exámenes asignados → 403" y "Proctor accede a su examen asignado"; añade scenario "Proctor accede a cualquier examen activo → permitido". El scoping del revisor (jurisdicción) y el gate de acceso a evidencia **no cambian**.
- **`backend/app/domain/auth/authorization.py`**: función `autorizar_proctor_sobre_examen` — eliminar la restricción de asignación; el proctor con MFA satisfecho accede a cualquier examen. El parámetro `examenes_asignados` se vuelve obsoleto.
- **`backend/app/application/auth/authorization_service.py`**: el método `autorizar_proctor` del `ContextualAuthorizationService` ya no necesita resolver asignaciones para el proctor; se simplifica (o se elimina, dejando solo `autorizar_revisor` y `acceder_a_evidencia`).
- **Tests**: actualizar `test_auth_rbac_contextual.py` y `test_auth_contextual_service.py` — los tests de "proctor sobre examen no asignado → ForbiddenError" deben eliminarse o invertirse; añadir test "proctor global → siempre autorizado (con MFA)". Sin mocks de DB.
- **DPIA (nota)**: el diseño registra explícitamente que el alcance global del proctor **relaja el principio de mínimo privilegio** y exige justificación documentada en el acuerdo de proctoring (C-01).

## Capabilities

### New Capabilities

*(ninguna — este change no introduce una capability nueva; modifica una existente)*

### Modified Capabilities

- `contextual-rbac`: el proctor deja de estar scoped a asignaciones y pasa a tener alcance global sobre exámenes; el revisor sigue scoped a su jurisdicción y el gate de evidencia no cambia.

## Impact

- **KB**: `knowledge-base/03_actores_y_roles.md`, `knowledge-base/05_reglas_de_negocio.md`
- **Delta spec**: `openspec/changes/c-50-proctor-alcance-global/specs/contextual-rbac/spec.md`
- **Código dominio**: `backend/app/domain/auth/authorization.py` (`autorizar_proctor_sobre_examen`)
- **Código aplicación**: `backend/app/application/auth/authorization_service.py` (`ContextualAuthorizationService.autorizar_proctor`)
- **Tests**: `backend/tests/test_auth_rbac_contextual.py`, `backend/tests/test_auth_contextual_service.py`
- **Dependencia de riesgo**: C-01 (`acuerdo-proctoring-dpia`) — el DPIA debe reflejar la relajación del mínimo privilegio; este change no puede considerarse gobernanza-completo hasta que C-01 lo absorba
- **Sin cambios en**: lógica del revisor, gate de evidencia, MFA enforcement, infraestructura de Keycloak, paneles, ingesta de eventos
