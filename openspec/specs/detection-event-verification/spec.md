# detection-event-verification Specification

## Purpose
TBD - created by archiving change c-23-admin-mediapipe-test-harness. Update Purpose after archive.
## Requirements
### Requirement: Log de eventos discretos capturados por el harness
El sistema SHALL mostrar en el harness un log ordenado cronológicamente (más reciente primero) de todos los `DiscreteEvent` emitidos por `StateTransitionRules` durante la sesión activa, incluyendo: `tipo`, `severidad`, `ts_ms` (formateado como tiempo relativo desde el inicio de la sesión), `payload` serializado, y flag `trigger_evidence`.

#### Scenario: Regla dispara evento por ausencia de rostro sostenida
- **WHEN** `StateTransitionRules.process()` produce un `DiscreteEvent` de tipo `rostro_ausente`
- **THEN** el log SHALL mostrar una nueva entrada con tipo="rostro_ausente", severidad="media", payload con `sostenido_ms`, e indicación visual del flag `trigger_evidence=false`

#### Scenario: Regla dispara evento de alta severidad (múltiples rostros)
- **WHEN** `StateTransitionRules.process()` produce un `DiscreteEvent` de tipo `multiples_rostros` con `trigger_evidence=true`
- **THEN** el log SHALL resaltar la entrada con color de alerta alta y mostrar el badge "dispara evidencia" junto al tipo

#### Scenario: Sesión sin eventos en los primeros 10 segundos
- **WHEN** el harness lleva activo más de 10 segundos sin que ninguna regla haya disparado
- **THEN** el log SHALL mostrar el mensaje "Sin eventos aún — señales dentro de umbrales" en lugar de una lista vacía

### Requirement: Confirmación de que el EventSink registró cada evento
El sistema SHALL confirmar visualmente, por cada entrada del log, que el `EventSink` local procesó el evento correctamente, mostrando un indicador de estado: "emitido al sink" (llamada a `sendEvent` completada sin excepción) o "error en sink" (excepción capturada, con mensaje).

#### Scenario: EventSink procesa el evento sin error
- **WHEN** `VisionPipeline.emit()` llama a `sink.sendEvent()` y la promesa resuelve sin excepción
- **THEN** la entrada del log SHALL mostrar el indicador "✓ emitido" en verde junto al evento

#### Scenario: EventSink lanza excepción al procesar un evento
- **WHEN** `sink.sendEvent()` rechaza la promesa con una excepción
- **THEN** la entrada del log SHALL mostrar el indicador "✗ error" en rojo con el mensaje de la excepción, SIN crashear el pipeline

### Requirement: Confirmación de que el evento llega a store.anomaliasVivo
El sistema SHALL mostrar un contador en tiempo real de cuántos eventos han sido empujados a `store.anomaliasVivo` durante la sesión del harness, y SHALL resaltar la entrada del log correspondiente cuando el evento se refleja en el store (comparando id).

#### Scenario: Evento empujado al store
- **WHEN** el harness llama a `pushAnomalia()` tras emitir un evento y el store Zustand actualiza `anomaliasVivo`
- **THEN** el contador SHALL incrementarse en 1 y la entrada del log SHALL marcarse como "en store"

#### Scenario: Store lleno (límite 50 anomalías)
- **WHEN** `anomaliasVivo` ya contiene 50 entradas y se emite un nuevo evento
- **THEN** el log del harness SHALL indicar que el store recortó el evento más antiguo (badge "store: overflow, evento anterior descartado"), reflejando el comportamiento de `pushAnomalia`

### Requirement: Filtro por severidad en el log de eventos
El sistema SHALL proveer un control de filtro de severidad (multi-select: baseline, baja, media, alta, critica) que filtre las entradas del log sin borrar el historial acumulado.

#### Scenario: Admin filtra solo eventos de severidad alta y crítica
- **WHEN** el admin selecciona únicamente "alta" y "critica" en el filtro
- **THEN** el log SHALL mostrar solo los eventos con `severidad` en {"alta","critica"}, manteniendo el conteo total visible como "N eventos (M visibles)"

#### Scenario: Admin limpia todos los filtros
- **WHEN** el admin selecciona todas las severidades o hace clic en "Mostrar todos"
- **THEN** el log SHALL mostrar todos los eventos acumulados en la sesión

### Requirement: Exportación del log de eventos a JSON
El sistema SHALL proveer un botón "Exportar log" que descargue como archivo JSON el historial completo de `DiscreteEvent` de la sesión actual del harness, incluyendo el config de `TransitionConfig` usado y el timestamp de inicio de sesión.

#### Scenario: Admin exporta log con eventos capturados
- **WHEN** el admin hace clic en "Exportar log" con al menos un evento en el log
- **THEN** el navegador SHALL descargar un archivo `detection-harness-log-<timestamp>.json` con el array de eventos, el `TransitionConfig` activo y el `session_start_ts`

#### Scenario: Admin exporta log vacío
- **WHEN** el admin hace clic en "Exportar log" sin ningún evento en el log
- **THEN** el sistema SHALL exportar igual el JSON (con array vacío) y mostrar un toast informando que el log está vacío

