## MODIFIED Requirements

### Requirement: AlumnoDashboard usa componentes extraídos
El componente `AlumnoDashboard` SHALL delegar el renderizado de accesos rápidos a `QuickAccessCard` y el renderizado de inscripciones próximas a `ExamenProximoCard`. La pantalla mantiene toda la lógica de estado (carga de inscripciones, gate `puedeRendir`/`razonBloqueo`) y solo compone los componentes visuales.

La pantalla SHALL quedar en ≤ 120 líneas luego del refactor.

Los datos de inscripciones y gate se cargan exactamente igual que hoy (`Promise.all([api.misInscripciones(), api.puedeRendir()])`). El filtraje de `proximos` (estados `inscripto` o `habilitado`) permanece en la pantalla.

#### Scenario: Accesos rápidos renderizan QuickAccessCard
- **WHEN** se monta `AlumnoDashboard`
- **THEN** la sección "Acceso rápido" renderiza 3 instancias de `QuickAccessCard` para Mis materias, Mis exámenes y Mi perfil, cada una con `onClick` que navega a la ruta correspondiente

#### Scenario: Próximos exámenes renderizan ExamenProximoCard
- **WHEN** hay inscripciones con estado `inscripto` o `habilitado`
- **THEN** cada inscripción se renderiza con `ExamenProximoCard`

#### Scenario: Banner de perfil incompleto no cambia
- **WHEN** `puedeRendir === false`
- **THEN** se muestra el banner de advertencia inline (no extraído a componente) con el `razonBloqueo` y el botón "Completar perfil"

#### Scenario: Estado vacío no cambia
- **WHEN** no hay inscripciones próximas
- **THEN** se muestra `Card` con `event_busy` + texto + botón "Inscribite a un examen" (comportamiento sin cambio)
