## MODIFIED Requirements

### Requirement: AlumnoMaterias usa componentes extraídos
El componente `AlumnoMaterias` SHALL delegar el renderizado del árbol Materia→Comisión→Examen a `MateriaCard`, `ComisionRow` y `ExamenCard`. La pantalla mantiene toda la lógica de estado (selección, carga por nivel, gate C-26) y compone los componentes.

La pantalla SHALL quedar en ≤ 120 líneas luego del refactor.

El flujo C-26 (acuse antes de inscribir) permanece intacto: `iniciarInscripcion` → `setExamenPendienteAcuse` → render de `AcuseExamen` → `completarInscripcionTrasAcuse`. Los callbacks de los componentes disparan exactamente la misma lógica.

#### Scenario: Lista de materias usa MateriaCard
- **WHEN** se cargan las materias disponibles
- **THEN** cada materia se renderiza con `MateriaCard`; `activa` es `true` solo para `materiaSeleccionada?.id === materia.id`

#### Scenario: Selección de materia
- **WHEN** el usuario clickea una `MateriaCard`
- **THEN** `onSelect` invoca `seleccionarMateria(materia)` con el mismo comportamiento toggle de hoy

#### Scenario: Árbol de comisiones
- **WHEN** una materia está activa y se cargan comisiones
- **THEN** `MateriaCard` renderiza `ComisionRow` por cada comisión; `ComisionRow.activa` es `true` solo para `comisionSeleccionada?.id === comision.id`

#### Scenario: Inscribir desde ExamenCard dispara acuse C-26
- **WHEN** el usuario clickea "Inscribirme" en un `ExamenCard`
- **THEN** `onInscribir(examen.id)` invoca `iniciarInscripcion(examen.id)` que establece `examenPendienteAcuse` y renderiza `AcuseExamen` (flujo C-26 sin cambio)

#### Scenario: Estado cargando materias
- **WHEN** `cargandoMaterias === true`
- **THEN** se muestra `Card` con spinner — igual que hoy (no delegado a componente)
