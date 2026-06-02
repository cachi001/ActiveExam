## ADDED Requirements

### Requirement: El formulario valida los campos requeridos de forma inline sin alert()
El sistema SHALL validar cada campo requerido y con rango de `ConfigureExam.tsx` en tiempo real, mostrando mensajes de error directamente bajo el control afectado mediante el slot `error` de `FormField`. No SHALL usar `alert()`, `window.confirm()` ni ningún diálogo nativo del browser para comunicar errores de validación.

#### Scenario: Campo nombre vacío muestra error inline
- **WHEN** el campo nombre está vacío (o solo espacios en blanco)
- **THEN** se muestra el mensaje "El nombre del examen es requerido" bajo el input de nombre
- **THEN** el botón Guardar permanece deshabilitado

#### Scenario: Campo cátedra vacío muestra error inline
- **WHEN** el campo cátedra está vacío (o solo espacios en blanco)
- **THEN** se muestra el mensaje "La cátedra es requerida" bajo el input de cátedra
- **THEN** el botón Guardar permanece deshabilitado

#### Scenario: Fecha de inicio en el pasado muestra error inline
- **WHEN** el campo inicio contiene una fecha anterior a (now + 5 minutos)
- **THEN** se muestra el mensaje "El inicio debe ser en el futuro" bajo el input de inicio
- **THEN** el botón Guardar permanece deshabilitado

#### Scenario: Formulario válido habilita el botón Guardar
- **WHEN** nombre no vacío, cátedra no vacía, inicio en el futuro, y todos los rangos son válidos
- **THEN** el botón Guardar está habilitado (no disabled)
- **THEN** no hay mensajes de error visibles en el formulario

#### Scenario: Botón Guardar deshabilitado impide el submit
- **WHEN** el formulario tiene al menos un error de validación
- **THEN** el botón Guardar tiene el atributo `disabled`
- **THEN** hacer clic en el botón no invoca `api.saveExam()`

### Requirement: El formulario muestra un preview del examen antes de confirmar
El sistema SHALL mostrar una tarjeta `ExamenResumenCard` siempre visible en la tercera sección del formulario, que refleje en tiempo real la configuración actual del examen en lenguaje claro. La tarjeta SHALL actualizarse sin demora cada vez que el admin modifique cualquier campo.

#### Scenario: Preview muestra nombre y cátedra del examen
- **WHEN** el admin escribe un nombre y una cátedra en el formulario
- **THEN** el componente `ExamenResumenCard` refleja el nombre y la cátedra actualizados
- **THEN** los campos sin completar se muestran como "—"

#### Scenario: Preview muestra la fecha de inicio formateada en español
- **WHEN** el admin selecciona una fecha/hora de inicio válida
- **THEN** el preview muestra la fecha formateada en español (ej. "2 jun 2026, 09:00")
- **THEN** no muestra el string ISO crudo

#### Scenario: Preview muestra la cantidad de detectores activos con aclaración L2.5
- **WHEN** el admin activa o desactiva detectores en DetectoresSelector
- **THEN** el preview muestra "N de M detectores activos"
- **THEN** el preview incluye la aclaración "priorizan sesiones para revisión humana, no sancionan"

#### Scenario: Preview muestra retención con referencia legal
- **WHEN** el admin configura los días de retención
- **THEN** el preview muestra "{N} días (Ley 25.326)"

#### Scenario: Preview muestra umbral de cola de revisión
- **WHEN** el admin ajusta el umbral de score
- **THEN** el preview muestra "Umbral de cola de revisión: {N}%"

### Requirement: Los detectores activos se gestionan mediante el componente DetectoresSelector
El sistema SHALL proveer el componente `DetectoresSelector` (`frontend/src/screens/admin/components/DetectoresSelector.tsx`) que encapsule la lista de checkboxes de detectores activos. El componente SHALL mostrar un resumen de cuántos detectores están activos del total disponible.

#### Scenario: DetectoresSelector muestra todos los detectores disponibles
- **WHEN** se renderiza `DetectoresSelector` con un conjunto de detectores activos
- **THEN** se muestra un checkbox por cada detector en la constante `DETECTORES`
- **THEN** los detectores incluidos en `value` aparecen marcados

#### Scenario: DetectoresSelector actualiza la selección al marcar o desmarcar
- **WHEN** el admin hace clic en un checkbox de detector
- **THEN** se invoca `onChange` con el nuevo array de detectores
- **THEN** el detector se agrega al array si estaba desmarcado, o se elimina si estaba marcado

#### Scenario: DetectoresSelector muestra resumen de activos
- **WHEN** hay N detectores activos de un total de M
- **THEN** el componente muestra el texto "N de M detectores activos"

### Requirement: El formulario organiza los campos en tres secciones con SectionTitle
El sistema SHALL organizar los campos de `ConfigureExam.tsx` en tres secciones visuales delimitadas por el componente `SectionTitle`: "Información del examen", "Parámetros de proctoring" y "Resumen del examen". Los botones Cancelar y Guardar SHALL ubicarse después de la tercera sección.

#### Scenario: Secciones visibles en el formulario
- **WHEN** el admin navega a la pantalla de creación o edición de examen
- **THEN** se renderizan tres secciones con sus títulos: "Información del examen", "Parámetros de proctoring" y "Resumen del examen"
- **THEN** los botones Cancelar y Guardar aparecen al final, debajo de la sección de resumen

### Requirement: El guardado muestra estado loading durante la operación
El sistema SHALL mostrar un spinner e indicador textual ("Guardando…") en el botón Guardar durante el tiempo que `api.saveExam()` está en progreso. El botón SHALL estar deshabilitado durante este período para evitar doble submit.

#### Scenario: Botón muestra loading durante guardado
- **WHEN** el admin hace clic en Guardar con el formulario válido
- **THEN** el botón Guardar muestra el icono spinner y el texto "Guardando…"
- **THEN** el botón está deshabilitado durante la operación asíncrona

#### Scenario: Navegación tras guardado exitoso
- **WHEN** `api.saveExam()` resuelve sin error
- **THEN** la aplicación navega a `/admin/examenes`
