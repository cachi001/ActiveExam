## MODIFIED Requirements

### Requirement: Harness opera en modo diagnóstico puro (sin red) por defecto
El harness diagnóstico de administradores SHALL operar por defecto en modo diagnóstico sin emisión HTTP, preservando la restricción de aislamiento D-4 (C-23). El modo de grabación es opt-in mediante un botón explícito. Sin iniciar grabación, el comportamiento es idéntico al anterior: LocalHarnessEventSink air-gapped, sin llamadas HTTP, sin screenshots.

#### Scenario: Inicio del harness sin grabación
- **WHEN** el usuario inicia el harness y no presiona "Grabar sesión"
- **THEN** no se realiza ninguna llamada HTTP; el diagnóstico y el log funcionan exactamente como antes de C-46

#### Scenario: Modo grabar es opt-in
- **WHEN** el harness está en estado running
- **THEN** el botón "Grabar sesión" es visible pero no activo; el modo de grabación está en 'idle'

### Requirement: El harness muestra el sessionId activo durante grabación
Cuando `recordMode === 'recording'`, el harness SHALL mostrar el `sessionId` activo (truncado a 12 caracteres) en el área de controles para permitir al administrador correlacionar el log con la sesión en el backend.

#### Scenario: SessionId visible durante grabación
- **WHEN** `recordMode === 'recording'`
- **THEN** se muestra "Sesión: {sessionId.slice(0,12)}…" junto al contador de eventos grabados

#### Scenario: SessionId no visible fuera de grabación
- **WHEN** `recordMode !== 'recording'`
- **THEN** no se muestra ningún sessionId en la UI del harness
