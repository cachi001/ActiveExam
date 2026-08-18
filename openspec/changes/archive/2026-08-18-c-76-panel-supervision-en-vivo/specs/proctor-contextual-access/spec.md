## MODIFIED Requirements

### Requirement: Acceso al panel del proctor restringido por rol
El acceso a las acciones y vistas de supervisión SHALL estar restringido por **rol** (RBAC) y, para el tutor, por **pertenencia a la comisión**. Los roles `coordinador` y `admin_sistema` acceden globalmente a la lista/detalle de sesiones, a las pausas pendientes y su resolución, y a las observaciones. El rol `tutor` accede a lo mismo **acotado a las comisiones donde es docente** (`asignar_docente`, C-73 §9). El rol `revisor` accede a las sesiones de su jurisdicción. El rol `proctor` **ya no existe**. Las sesiones `modo='examen'` (evidencia académica real) NUNCA se pueden eliminar, ni siquiera por `admin_sistema` (cadena de custodia, regla dura #6/#7); solo las sesiones `modo='test'` (diagnóstico, sin examen vinculado) son eliminables, y esa acción queda auditada. El **veredicto** (`revisar_sesion`) queda restringido a `coordinador`, `revisor` y `admin_sistema`; el tutor NO lo tiene.

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
- **SUPERSEDED**: reemplazado por los dos escenarios de abajo — ya NO existe una excepción de "admin puede eliminar evidencia académica"; la cadena de custodia no admite excepción por rol (regla dura #6/#7). El admin solo puede eliminar sesiones `modo='test'` (diagnóstico, sin evidencia académica real).

#### Scenario: Ninguna sesión de examen real se puede eliminar, ni siquiera el admin
- **WHEN** cualquier usuario, incluido `admin_sistema`, intenta eliminar una sesión `modo='examen'`
- **THEN** el acceso es rechazado (409/400) — cadena de custodia, no hay excepción por rol

#### Scenario: El admin elimina una sesión de diagnóstico (modo test)
- **WHEN** un usuario con rol `admin_sistema` elimina una sesión `modo='test'` (sin examen real vinculado)
- **THEN** la sesión se borra y la acción queda auditada bajo el módulo `SESIONES`

#### Scenario: El proctor accede a la supervisión por su rol
- **SUPERSEDED**: el rol `proctor` fue eliminado del sistema. Reemplazado por los escenarios de Tutor/Coordinador de arriba.

#### Scenario: El estudiante no accede a las acciones del proctor
- **SUPERSEDED**: renombrado a "El estudiante no accede a las acciones de supervisión" (arriba), mismo comportamiento, sin referencia al rol `proctor` eliminado.
