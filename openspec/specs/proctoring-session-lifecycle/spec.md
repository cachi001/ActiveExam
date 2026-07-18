# proctoring-session-lifecycle Specification

## Purpose
TBD - created by archiving change c-64-persistencia-eventos-biometria-sesion. Update Purpose after archive.
## Requirements
### Requirement: La sesión de proctoring se crea antes del paso biométrico
El sistema SHALL crear la sesión de proctoring al inicio del flujo del alumno (en `ExamenLayout` o su equivalente), antes de que el alumno llegue al paso de verificación biométrica (paso 3). El `proctoringSessionId` SHALL estar disponible en el store Zustand cuando `Biometria.tsx` complete la verificación. Si la sesión ya existe en el store, el sistema NO SHALL crear una nueva sesión (idempotencia).

#### Scenario: Sesión creada antes del paso biométrico
- **WHEN** el alumno inicia el flujo de examen (monta el layout del flujo)
- **THEN** se llama `api.crearSesionProctoring` con `modo='examen'` y `exam_id` del examen activo
- **THEN** el `proctoringSessionId` se almacena en el store Zustand antes de que el alumno llegue al paso 3

#### Scenario: Idempotencia — no crear sesión duplicada
- **WHEN** el componente se re-renderiza y `proctoringSessionId` ya está en el store
- **THEN** el sistema NO llama `api.crearSesionProctoring` nuevamente
- **THEN** el `proctoringSessionId` existente se conserva

#### Scenario: Biometría persistida porque la sesión ya existe
- **WHEN** el alumno completa la verificación biométrica en el paso 3
- **THEN** `proctoringSessionId` es distinto de null
- **THEN** `api.enviarBiometriaProctoring(proctoringSessionId, {...})` se llama exitosamente
- **THEN** aparece una fila en `proctoring_biometria` asociada a la sesión

### Requirement: La sesión de proctoring se finaliza al cerrar el examen
El sistema SHALL llamar `PATCH /proctoring/sessions/{id}/finalizar` desde `Cierre.tsx` al montar la pantalla, seteando `finalizada_en` a la hora actual en el backend. La operación SHALL ser idempotente: si `finalizada_en` ya está seteado, el endpoint responde 200 sin modificar la sesión.

#### Scenario: Finalización exitosa al renderizar Cierre
- **WHEN** el alumno llega a la pantalla de cierre (`Cierre.tsx` monta)
- **THEN** se llama `api.finalizarSesionProctoring(proctoringSessionId)`
- **THEN** la sesión en la DB tiene `finalizada_en` distinto de null

#### Scenario: Finalización idempotente
- **WHEN** `PATCH /proctoring/sessions/{id}/finalizar` se llama sobre una sesión ya finalizada
- **THEN** el endpoint responde 200 con los datos actuales sin modificar `finalizada_en`

#### Scenario: Cierre no bloquea si la finalización falla
- **WHEN** `api.finalizarSesionProctoring` lanza un error de red
- **THEN** `Cierre.tsx` muestra la pantalla de cierre igualmente (degradación silenciosa)
- **THEN** no se muestra ningún error al alumno

### Requirement: Cierre.tsx muestra conteos reales del backend
El sistema SHALL obtener el conteo de eventos, score y estado de biometría desde `GET /proctoring/sessions/{id}` al montar `Cierre.tsx`, reemplazando los valores locales del store Zustand. Si el GET falla, SHALL mostrar "—" para los conteos reales sin bloquear la pantalla.

#### Scenario: Conteos reales reemplazando el store
- **WHEN** `Cierre.tsx` monta después de un examen real
- **THEN** se llama `GET /proctoring/sessions/{proctoringSessionId}`
- **THEN** "Señales registradas" muestra el `total_eventos` del backend (no `anomaliasVivo.length`)
- **THEN** "Score de prioridad" muestra el `score` del backend

#### Scenario: Fallback si el GET falla
- **WHEN** `GET /proctoring/sessions/{id}` falla (red caída o 404)
- **THEN** "Señales registradas" muestra "—" o el valor del store local como fallback
- **THEN** la pantalla de cierre se muestra igualmente sin error visible al alumno

### Requirement: Backend expone endpoint PATCH /sessions/{id}/finalizar
El sistema SHALL implementar `PATCH /proctoring/sessions/{session_id}/finalizar` en el router slim. El endpoint SHALL setear `finalizada_en = datetime.utcnow()` si y solo si `finalizada_en IS NULL`. Responde 200 con `{ id, finalizada_en }` si existe la sesión, 404 si no.

#### Scenario: Endpoint finaliza sesión correctamente
- **WHEN** se llama `PATCH /proctoring/sessions/{id}/finalizar` sobre una sesión existente con `finalizada_en = null`
- **THEN** la DB actualiza `finalizada_en` al timestamp actual
- **THEN** responde 200 con `{ "id": "...", "finalizada_en": "..." }`

#### Scenario: 404 si la sesión no existe
- **WHEN** se llama `PATCH /proctoring/sessions/{id_inexistente}/finalizar`
- **THEN** el endpoint responde 404 con detalle "Sesion no encontrada"

### Requirement: La reanudación de una sesión emite su evento server-side

Cuando el sistema reanuda una sesión activa existente en vez de crear una nueva, SHALL emitir el evento de reanudación correspondiente **desde el servidor**, en el momento del resume. El evento SHALL NOT depender de que el cliente lo reporte: el servidor sabe con certeza que reanudó, y un cliente modificado SHALL ser incapaz de suprimir, falsear o desactivar el registro (regla dura de dominio #6 — el sensor que reportaría la conducta es el mismo que la ejecuta).

#### Scenario: Reanudar emite el evento sin intervención del cliente

- **WHEN** un alumno vuelve a abrir un examen y el sistema reanuda su sesión activa existente
- **THEN** el sistema emite el evento de reanudación server-side, asociado a esa sesión

#### Scenario: Un cliente modificado no puede suprimir el registro

- **WHEN** un cliente manipulado reanuda una rendición sin reportar ningún evento de recarga
- **THEN** el evento de reanudación queda registrado igualmente, porque lo emite el servidor

#### Scenario: Crear una sesión nueva no emite evento de reanudación

- **WHEN** un alumno arranca una rendición y no existe sesión activa previa para ese examen
- **THEN** se crea una sesión nueva y NO se emite evento de reanudación

### Requirement: El evento de reanudación registra la duración de la ausencia

El evento de reanudación SHALL registrar la **duración de la ausencia** medida server-side, y esa duración SHALL determinar el tipo emitido según el catálogo (reanudación rápida vs. tardía). La duración SHALL quedar disponible para el revisor humano, porque es la señal que distingue una falla de infraestructura de una consulta externa: la reanudación por sí sola NO SHALL interpretarse como conducta indebida.

#### Scenario: Ausencia breve emite reanudación rápida

- **WHEN** una sesión se reanuda tras una ausencia breve
- **THEN** el evento emitido es el de reanudación rápida, con la duración registrada

#### Scenario: Ausencia prolongada emite reanudación tardía

- **WHEN** una sesión se reanuda tras una ausencia prolongada
- **THEN** el evento emitido es el de reanudación tardía, con la duración registrada

#### Scenario: La duración es visible para el revisor

- **WHEN** un revisor humano abre el contexto de una sesión que registró reanudaciones
- **THEN** puede ver cuánto duró cada ausencia, no solo que hubo una reanudación

### Requirement: La reanudación no altera el deadline de la rendición

La reanudación de una sesión SHALL conservar `creada_en` inmutable y SHALL NOT extender, pausar ni reiniciar el deadline efectivo. Reanudar SHALL restaurar el estado de la rendición (respuestas ya persistidas y tiempo restante real), NOT otorgar tiempo adicional.

#### Scenario: Reanudar conserva el ancla temporal

- **WHEN** el sistema reanuda una sesión activa
- **THEN** devuelve la misma sesión con el mismo `creada_en` y el mismo deadline efectivo que antes de la interrupción

#### Scenario: Reanudar restaura las respuestas ya guardadas

- **WHEN** un alumno reanuda una rendición dentro del plazo
- **THEN** las respuestas que había persistido siguen disponibles y puede continuar con el tiempo restante real

