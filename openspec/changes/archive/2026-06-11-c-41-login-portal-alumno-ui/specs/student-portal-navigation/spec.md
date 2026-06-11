## MODIFIED Requirements

### Requirement: AlumnoMisExamenes usa InscripcionCard
El componente `AlumnoMisExamenes` SHALL delegar el renderizado de cada inscripción a `InscripcionCard`. La pantalla mantiene toda la lógica de estado (carga de inscripciones, evaluación de gates C-26, flujo de acuse) y compone el componente.

La pantalla SHALL quedar en ≤ 110 líneas luego del refactor.

El gate en capas (C-26) permanece intacto: `gatesPorExamen` se evalúa en la pantalla y se pasa como prop `gate` a `InscripcionCard`. Los callbacks `onRendir`, `onCompletarAcuse` y `onIrAPerfil` mapean a `handleRendir`, `setExamenCompletandoAcuse` y `navigate('/alumno/perfil')` respectivamente.

#### Scenario: Lista de inscripciones usa InscripcionCard
- **WHEN** se cargan las inscripciones y gates
- **THEN** cada inscripción se renderiza con `InscripcionCard`, pasando `gate={gatesPorExamen[insc.examen_id]}`, `verificando={verificandoId === insc.id}`, y los 3 callbacks

#### Scenario: Gate C-26 — acuse faltante se muestra en InscripcionCard
- **WHEN** `gate.codigo === "acuse_examen_faltante"`
- **THEN** `InscripcionCard` muestra el banner de acuse con botón "Completar acuse del examen"; al clickear invoca `onCompletarAcuse` que llama `setExamenCompletandoAcuse(insc.examen_id)` en la pantalla

#### Scenario: Pantalla AcuseExamen se muestra desde Mis Exámenes
- **WHEN** `examenCompletandoAcuse` es no-null
- **THEN** la pantalla renderiza `AcuseExamen` (sin cambio en flujo C-26)

#### Scenario: Re-evaluación del gate tras completar acuse
- **WHEN** el alumno completa el acuse (`handleAcuseCompletado`)
- **THEN** se llama `api.puedeRendir(examenId)` y se actualiza `gatesPorExamen` para ese examen (sin cambio en lógica)

#### Scenario: Estado vacío sin inscripciones
- **WHEN** `inscripciones.length === 0`
- **THEN** se muestra `Card` con `event_busy` + botón "Ver materias disponibles" (sin cambio; no delegado a componente)
