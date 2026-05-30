# Spec — contextual-rbac

> Capacidad de **autorización contextual** sobre 7 roles. Los permisos no son globales: proctor solo exámenes asignados, revisor solo su jurisdicción (`03` §RBAC). Su Done es: el acceso fuera de contexto se rechaza aunque el rol sea correcto.

## ADDED Requirements

### Requirement: Permisos contextuales sobre los 7 roles funcionales
La autorización SHALL evaluar el **contexto** además del rol sobre los 7 roles (estudiante, proctor, revisor académico, coordinador, admin de exámenes, admin del sistema, auditor — `03`), de modo que tener el rol no concede acceso global al recurso.

#### Scenario: Proctor accede solo a exámenes asignados
- **WHEN** un proctor solicita una sesión de un examen que **no** está en su Asignación (C-05)
- **THEN** el sistema rechaza el acceso (403), aunque el rol proctor sea válido

#### Scenario: Proctor accede a su examen asignado
- **WHEN** un proctor solicita una sesión de un examen que **sí** está en su Asignación
- **THEN** el acceso es concedido (lectura/observaciones/mensajes/cierre forzado, `03`)

#### Scenario: Revisor no cruza su jurisdicción
- **WHEN** un revisor académico intenta abrir una sesión flaggeada **fuera** de su jurisdicción
- **THEN** el sistema rechaza el acceso (403)

### Requirement: Acceso a evidencia auditado con propósito declarado
El acceso a evidencia por proctor/revisor SHALL registrar en el audit log (C-05) el propósito declarado del acceso, conforme a `03` §RBAC; el sistema **nunca sanciona automáticamente** (L2.5) — solo controla el acceso.

#### Scenario: Apertura de evidencia auditada
- **WHEN** un revisor abre la evidencia/contexto de una sesión flaggeada de su jurisdicción
- **THEN** se registra una entrada en el audit log con actor, timestamp, recurso y propósito declarado

#### Scenario: El sistema no decide la sanción
- **WHEN** se evalúa el acceso a una sesión flaggeada
- **THEN** la autorización solo controla el acceso al recurso; la decisión disciplinaria final es siempre humana (L2.5)
