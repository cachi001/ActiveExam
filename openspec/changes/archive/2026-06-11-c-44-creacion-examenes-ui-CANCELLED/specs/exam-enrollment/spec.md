## MODIFIED Requirements

### Requirement: El admin puede guardar la configuración de un examen con validación inline
El sistema SHALL permitir al administrador guardar la configuración de un examen únicamente cuando todos los campos del formulario son válidos (nombre no vacío, cátedra no vacía, inicio en el futuro, todos los rangos dentro de sus límites). El guardado SHALL invocarse mediante `api.saveExam()` sin modificar el modelo `Examen` ni la lógica de guardado existente. La validación SHALL ser exclusivamente del lado del cliente en este change.

#### Scenario: Guardado exitoso con formulario válido
- **WHEN** todos los campos del formulario son válidos
- **THEN** el admin puede hacer clic en el botón Guardar (habilitado)
- **THEN** se invoca `api.saveExam()` con `{ ...form, estado: 'programado' }` si el estado es `borrador`
- **THEN** la aplicación navega a `/admin/examenes` al completar

#### Scenario: Guardado bloqueado cuando el formulario tiene errores
- **WHEN** algún campo del formulario no cumple las reglas de validación
- **THEN** el botón Guardar está deshabilitado
- **THEN** no se invoca `api.saveExam()`

#### Scenario: Guardado bloqueado durante la operación asíncrona
- **WHEN** `api.saveExam()` está en progreso (`guardando === true`)
- **THEN** el botón Guardar está deshabilitado
- **THEN** el botón muestra indicador visual de carga ("Guardando…")
