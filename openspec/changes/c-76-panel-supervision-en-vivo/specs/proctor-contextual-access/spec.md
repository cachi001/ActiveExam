## MODIFIED Requirements

### Requirement: Acceso al panel de supervisión restringido por rol y comisión
El acceso a las acciones y vistas de supervisión SHALL estar restringido por **rol** (RBAC) y, para el tutor, por **pertenencia a la comisión**. Los roles `coordinador` y `admin_sistema` acceden globalmente a la lista/detalle de sesiones, a las pausas pendientes y su resolución, y a las observaciones. El rol `tutor` accede a lo mismo **acotado a las comisiones donde es docente** (`asignar_docente`, C-73 §9). El rol `revisor` accede a las sesiones de su jurisdicción. El rol `proctor` **ya no existe**. La eliminación de evidencia (cadena de custodia, regla dura #6) SHALL quedar restringida a `admin_sistema`. El **veredicto** (`revisar_sesion`) queda restringido a `coordinador`, `revisor` y `admin_sistema`; el tutor NO lo tiene.

#### Scenario: Tutor accede a la supervisión de su comisión
- **WHEN** un usuario con rol `tutor` abre la supervisión de una sesión de una comisión donde es docente
- **THEN** ve y opera la lista/detalle de esa sesión y las pausas pendientes de la misma, pero NO ve el botón de veredicto

#### Scenario: Tutor no accede a comisiones ajenas
- **WHEN** un usuario con rol `tutor` intenta abrir la supervisión de una sesión de una comisión donde NO es docente
- **THEN** el acceso es rechazado (403)

#### Scenario: Coordinador accede globalmente y con veredicto
- **WHEN** un usuario con rol `coordinador` o `admin_sistema` abre la supervisión
- **THEN** ve y opera cualquier sesión, las pausas pendientes, y dispone de la acción de veredicto (`revisar_sesion`)

#### Scenario: El estudiante no accede a las acciones de supervisión
- **WHEN** un usuario con rol `estudiante` intenta leer/escribir observaciones o listar pausas pendientes
- **THEN** el acceso es rechazado (403)

#### Scenario: Solo el admin elimina evidencia
- **WHEN** un usuario sin rol `admin_sistema` intenta eliminar una sesión grabada
- **THEN** el acceso es rechazado (cadena de custodia)
