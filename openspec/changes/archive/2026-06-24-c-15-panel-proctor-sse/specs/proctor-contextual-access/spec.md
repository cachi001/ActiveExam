# Spec — proctor-contextual-access

> Control de acceso al panel del proctor por **rol** (RBAC). Lo entregado en el slim.
>
> DECISIÓN DEL DUEÑO (2026-06-23): "solo exámenes asignados" (RN-AU-07) queda
> **SUPERSEDED** — el proctor accede a TODAS las revisiones (mínimo privilegio sobre
> el set de pantallas, no aislamiento por asignación). El **MFA** (RN-AU-05) se
> difiere a `c-15b-panel-proctor-sse-transport` (el slim no emite segundo factor).

## ADDED Requirements

### Requirement: Acceso al panel del proctor restringido por rol
El acceso a las acciones y vistas del proctor SHALL estar restringido por **rol**
(RBAC): los roles `proctor` y `admin_sistema` acceden a la lista/detalle de sesiones,
a las pausas pendientes y a su resolución, y a las observaciones; el resto del flujo
del alumno requiere únicamente estar autenticado. La eliminación de evidencia
(cadena de custodia, regla dura #6) SHALL quedar restringida a `admin_sistema`.

#### Scenario: El proctor accede a la supervisión por su rol
- **WHEN** un usuario con rol `proctor` o `admin_sistema` abre la supervisión
- **THEN** ve y opera la lista/detalle de sesiones y las pausas pendientes

#### Scenario: El estudiante no accede a las acciones del proctor
- **WHEN** un usuario con rol `estudiante` intenta leer/escribir observaciones o
  listar pausas pendientes
- **THEN** el acceso es rechazado (403)

#### Scenario: Solo el admin elimina evidencia
- **WHEN** un usuario sin rol `admin_sistema` intenta eliminar una sesión grabada
- **THEN** el acceso es rechazado (cadena de custodia)
