## MODIFIED Requirements

### Requirement: Permisos contextuales sobre los 7 roles funcionales
La autorización SHALL evaluar el **contexto** además del rol sobre los roles funcionales (estudiante, revisor académico, coordinador, admin de exámenes, admin del sistema, auditor, tutor — `03`), de modo que tener el rol no concede acceso global al recurso. El rol `proctor` **ya no existe** en el sistema: la supervisión en vivo la ejerce el **tutor** (acotado a las comisiones donde es docente) y el **coordinador** (global); ninguno de ellos obtiene acceso global por el solo hecho de tener el rol.

#### Scenario: Tutor supervisa solo las sesiones de sus comisiones
- **WHEN** un tutor solicita una sesión de una comisión donde **no** está asignado como docente
- **THEN** el sistema rechaza el acceso (403), aunque el rol tutor tenga la capacidad `supervisar_vivo`

#### Scenario: Tutor accede a la sesión de su comisión
- **WHEN** un tutor solicita una sesión de una comisión donde **sí** está asignado como docente
- **THEN** el acceso es concedido (lectura/observaciones/mensajes/cierre forzado/aprobación de pausa, `03`), pero NO el veredicto

#### Scenario: Revisor no cruza su jurisdicción
- **WHEN** un revisor académico intenta abrir una sesión flaggeada **fuera** de su jurisdicción
- **THEN** el sistema rechaza el acceso (403)

#### Scenario: Proctor accede solo a exámenes asignados
- **SUPERSEDED**: el rol `proctor` fue eliminado del sistema (ver `## REMOVED Requirements` abajo). Este escenario queda documentado solo como referencia histórica; su comportamiento lo reemplazan los escenarios de Tutor de arriba.

#### Scenario: Proctor accede a su examen asignado
- **SUPERSEDED**: el rol `proctor` fue eliminado del sistema (ver `## REMOVED Requirements` abajo). Este escenario queda documentado solo como referencia histórica; su comportamiento lo reemplazan los escenarios de Tutor de arriba.

### Requirement: Acceso a evidencia auditado con propósito declarado
El acceso a evidencia por tutor/revisor/coordinador SHALL registrar en el audit log (C-05) el propósito declarado del acceso, conforme a `03` §RBAC; el sistema **nunca sanciona automáticamente** (L2.5) — solo controla el acceso.

#### Scenario: Apertura de evidencia auditada
- **WHEN** un revisor o coordinador abre la evidencia/contexto de una sesión flaggeada de su jurisdicción
- **THEN** se registra una entrada en el audit log con actor, timestamp, recurso y propósito declarado

#### Scenario: El sistema no decide la sanción
- **WHEN** se evalúa el acceso a una sesión flaggeada
- **THEN** la autorización solo controla el acceso al recurso; la decisión disciplinaria final es siempre humana (L2.5)

## REMOVED Requirements

### Requirement: Rol proctor como puesto de supervisión
**Reason**: El rol `proctor` no corresponde a un puesto institucional real. La supervisión en vivo la ejerce el tutor (docente de la comisión, acotado por pertenencia) y el veredicto lo emite el coordinador/revisor. Mantener `proctor` duplicaba autoridad y contradecía el modelo de pertenencia por comisión (C-73).
**Migration**: Eliminar `Rol.PROCTOR` del enum `Rol` y de `ROLES_CON_MFA`. Relevar los sujetos con rol `proctor` en la DB/IdP y remapearlos a `coordinador` (supervisión global) o `tutor` (docente de comisión) según su función real. Los JWT con claim `proctor` dejan de mapear a un rol de dominio (descartados por `parse_rol`); requiere re-login con el rol correcto.
