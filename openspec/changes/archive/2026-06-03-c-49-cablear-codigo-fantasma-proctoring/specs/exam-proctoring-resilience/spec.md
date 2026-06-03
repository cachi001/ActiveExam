## ADDED Requirements

### Requirement: El proctoring del examen persiste eventos en buffer antes de cada envío REST
El sistema SHALL instanciar un `CircularEventBuffer` respaldado por `IndexedDbEventBufferStore` en `useExamProctoring`. Antes de cada llamada a `api.enviarEventoProctoring`, el evento SHALL ser persistido en el buffer con su `id` y payload. Si IndexedDB no está disponible, el sistema SHALL degradar silenciosamente operando sin buffer (comportamiento actual).

#### Scenario: Evento se persiste antes del POST
- **WHEN** ocurre un evento discreto de proctoring durante el examen
- **THEN** el evento se almacena en el buffer IndexedDB antes de que se llame `api.enviarEventoProctoring`
- **THEN** si el POST falla, el evento permanece en el buffer para replay posterior

#### Scenario: IndexedDB no disponible — degradación silenciosa
- **WHEN** `IndexedDbEventBufferStore` lanza excepción al abrirse
- **THEN** el sistema opera sin buffer y continúa el flujo de examen sin interrupciones
- **THEN** no se lanza ningún error visible al alumno

### Requirement: El proctoring drena el buffer al recuperar conectividad
El sistema SHALL agregar listeners `online`/`offline` en `useExamProctoring`. Al recibir el evento `online`, el sistema SHALL invocar `drainAndReplay` usando un `ReplaySender` que llame a `api.enviarEventoProctoring(sessionId, event)` por cada evento pendiente en el buffer, en orden de secuencia `seq` ascendente.

#### Scenario: Drain exitoso al recuperar red
- **WHEN** el navegador dispara el evento `online` luego de un corte de conectividad
- **THEN** todos los eventos pendientes en el buffer se reenvían al backend en orden `seq` ascendente
- **THEN** los eventos confirmados se borran del buffer

#### Scenario: Listeners se limpian al desmontar el hook
- **WHEN** el componente que usa `useExamProctoring` se desmonta (examen finaliza o navega)
- **THEN** los listeners `online`/`offline` se remueven sin leaks de memoria

### Requirement: scorePropio se acumula en el store Zustand al detectar eventos
El sistema SHALL llamar `store.addScore(delta)` en el callback de evento de `useExamProctoring`, donde `delta` es el peso del evento según `PESO_SCORE[severidad]`. El valor de `store.scorePropio` SHALL reflejar la suma acumulada de todos los eventos de la sesión activa.

#### Scenario: Score crece con cada evento detectado
- **WHEN** el motor detecta un evento de severidad `alta` durante el examen
- **THEN** `store.scorePropio` se incrementa por `PESO_SCORE['alta']`
- **THEN** el valor es visible en la pantalla de cierre del examen

#### Scenario: Score no supera 100
- **WHEN** la suma acumulada de eventos excede 100
- **THEN** `store.scorePropio` se clampa en 100 (invariante del store existente via `Math.min`)
