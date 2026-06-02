## ADDED Requirements

### Requirement: Botón "Grabar sesión" visible cuando el harness está en estado running
El sistema SHALL mostrar un botón "Grabar sesión" en el área de controles del harness cuando `harnessState === 'running'` y `recordMode === 'idle'`. El botón es independiente del estado del motor de visión (funciona con motor real o con fallback). El modo de grabación es opt-in — el harness puede correr sin grabar.

#### Scenario: Botón visible al correr el harness
- **WHEN** el usuario inicia el harness (cámara activa)
- **THEN** aparece el botón "Grabar sesión" en el área de controles junto al botón "Detener"

#### Scenario: Botón no visible en idle/stopped
- **WHEN** `harnessState === 'idle'` o `harnessState === 'stopped'`
- **THEN** el botón "Grabar sesión" no se muestra

### Requirement: Iniciar grabación crea sesión en el backend
Al presionar "Grabar sesión", el sistema SHALL: (1) llamar `api.crearSesionProctoring('diagnostico', etiqueta)` para crear la sesión, (2) guardar el `sessionId` devuelto en un `useRef`, (3) cambiar `recordMode` a `'recording'`, (4) resetear el contador de eventos enviados a 0. Si la llamada falla, el harness continúa en modo diagnóstico sin grabar (muestra toast de error).

#### Scenario: Inicio de grabación exitoso
- **WHEN** el usuario presiona "Grabar sesión" y la API responde con sessionId
- **THEN** el estado cambia a "grabando", el contador de eventos enviados muestra 0 y el badge indica el sessionId

#### Scenario: Fallo al crear sesión
- **WHEN** el usuario presiona "Grabar sesión" y la API falla
- **THEN** se muestra un toast de error, el harness continúa en modo diagnóstico sin grabar

### Requirement: Cada evento captura screenshot y lo envía al backend
Cuando `recordMode === 'recording'` y se emite un evento desde el pipeline, el sistema SHALL: (1) capturar el frame actual del `<video>` usando `captureVideoFrame(videoRef.current, 0.7)`, (2) llamar `api.enviarEventoProctoring(sessionId, { tipo, severidad, ts_cliente, payload, screenshot_base64, face_count_cliente })`, (3) registrar el resultado (`veredicto_reinferencia`, `face_count_servidor`) en la entrada del log del harness, (4) incrementar el contador de eventos enviados. El paso (2) es asíncrono y fire-and-forget: no bloquea el loop de frames.

#### Scenario: Evento grabado con screenshot
- **WHEN** se emite un evento en modo grabación
- **THEN** el log muestra el evento con badge "grabado" y el veredicto_reinferencia del backend (o "⚠ sin red" si falló)

#### Scenario: Fallo de red no interrumpe el harness
- **WHEN** `enviarEventoProctoring` falla (timeout, error de red)
- **THEN** el evento igual se registra en el log local con badge "⚠ sin red", el loop de frames continúa sin interrupción

### Requirement: Estado visual de grabación — contador y badge
Cuando `recordMode === 'recording'`, el sistema SHALL mostrar: (a) un badge "● GRABANDO" con animación pulse junto al contador de eventos enviados (ej: "12 eventos grabados"), (b) el sessionId truncado (primeros 12 chars) para referencia. La cuenta se actualiza en tiempo real por cada evento enviado (exitoso o fallido con red).

#### Scenario: Counter se actualiza por evento
- **WHEN** se envía un evento (exitoso o con error de red)
- **THEN** el contador de "eventos grabados" se incrementa en 1

#### Scenario: Badge de grabación es visible y diferenciado
- **WHEN** `recordMode === 'recording'`
- **THEN** aparece badge con fondo de error/alerta, texto "GRABANDO" y punto pulsante

### Requirement: Detener grabación al presionar "Detener grabación"
El sistema SHALL mostrar un botón "Detener grabación" cuando `recordMode === 'recording'`. Al presionar: (1) cambia `recordMode` a `'stopped'`, (2) limpia el `sessionIdRef`, (3) muestra toast con resumen ("Grabación detenida — N eventos enviados"). El harness no se detiene — solo la grabación. El diagnóstico en vivo continúa.

#### Scenario: Detener grabación sin detener harness
- **WHEN** el usuario presiona "Detener grabación"
- **THEN** el badge de grabación desaparece, aparece toast con resumen, el harness sigue procesando frames

#### Scenario: Grabación se detiene automáticamente si el harness se detiene
- **WHEN** el usuario presiona "Detener" (stopHarness)
- **THEN** el modo de grabación se resetea a 'idle' y el sessionIdRef se limpia

### Requirement: Modo diagnóstico puro preservado intacto
El sistema SHALL garantizar que arrancar el harness sin presionar "Grabar sesión" produce exactamente el mismo comportamiento que antes de este change: LocalHarnessEventSink air-gapped, sin llamadas HTTP, sin screenshots. El modo grabación no cambia el pipeline, el sink ni los detectores de contexto.

#### Scenario: Harness sin grabación es idéntico al comportamiento previo
- **WHEN** el usuario inicia el harness y NO presiona "Grabar sesión"
- **THEN** no se realiza ninguna llamada HTTP, no se captura ningún screenshot, el log funciona exactamente igual que antes
