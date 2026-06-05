# Spec — contextual-rbac (delta C-50)

> Delta sobre la capability `contextual-rbac` introducida en C-06. Modifica el modelo de autorización del proctor: pasa de scoped-a-asignaciones a **alcance global** sobre todos los exámenes activos. El modelo del revisor (jurisdicción) y el gate de acceso a evidencia (MFA + audit log) no cambian.

## MODIFIED Requirements

### Requirement: Permisos contextuales sobre los 7 roles funcionales
La autorización SHALL evaluar el **contexto** además del rol sobre los 7 roles (estudiante, proctor, revisor académico, coordinador, admin de exámenes, admin del sistema, auditor — `03`), de modo que tener el rol no concede acceso global al recurso, **excepto para el proctor que tiene visión global de todos los exámenes activos**.

#### Scenario: Proctor accede a cualquier examen activo
- **WHEN** un proctor con MFA satisfecho solicita una sesión de cualquier examen activo
- **THEN** el acceso es concedido (lectura/observaciones/mensajes/cierre forzado, `03`), independientemente de asignaciones

#### Scenario: Proctor sin MFA es rechazado antes del acceso
- **WHEN** un proctor solicita una sesión de un examen sin haber satisfecho el segundo factor (MFA)
- **THEN** el sistema rechaza el acceso con error MFA requerido (antes de evaluar el rol o el examen)

#### Scenario: Revisor no cruza su jurisdicción
- **WHEN** un revisor académico intenta abrir una sesión flaggeada **fuera** de su jurisdicción
- **THEN** el sistema rechaza el acceso (403)

#### Scenario: Revisor dentro de su jurisdicción
- **WHEN** un revisor académico intenta abrir una sesión flaggeada **dentro** de su jurisdicción
- **THEN** el acceso es concedido

## REMOVED Requirements

### Requirement: Proctor scoped a exámenes asignados
**Reason**: Decisión del dueño del producto — el Proctor tiene alcance GLOBAL. El scoping a asignaciones revierte el principio de mínimo privilegio documentado en C-06 D3; la relajación queda justificada en el DPIA (C-01). Ver `knowledge-base/05_reglas_de_negocio.md` RN-AU-07 (actualizado) y `knowledge-base/03_actores_y_roles.md` (fila Proctor actualizada).
**Migration**: Eliminar la consulta al `AssignmentRepository` en `ContextualAuthorizationService.autorizar_proctor`; simplificar `autorizar_proctor_sobre_examen` en `backend/app/domain/auth/authorization.py` para no requerir `examenes_asignados`. Los tests de "proctor sobre examen no asignado → ForbiddenError" deben eliminarse y reemplazarse por "proctor global con MFA → siempre autorizado".
