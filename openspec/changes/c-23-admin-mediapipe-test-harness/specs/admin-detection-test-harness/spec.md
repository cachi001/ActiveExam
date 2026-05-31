## ADDED Requirements

### Requirement: Admin puede abrir el harness de detección sin examen activo
El sistema SHALL proveer una ruta protegida `/admin/detection-test` accesible solo para roles con permisos de administración (`admin_examenes`, `coordinador`) que instancie el pipeline de visión completo (motor `MediaPipeVisionEngine` + `VisionPipeline` + `StateTransitionRules` + `EventSink` local) usando la cámara del propio administrador, sin examen activo, sin sesión de alumno y sin posibilidad de emitir eventos al backend de producción.

#### Scenario: Acceso directo por URL sin rol admin
- **WHEN** un usuario sin rol `admin_examenes` ni `coordinador` navega a `/admin/detection-test`
- **THEN** el sistema SHALL redirigir al login o mostrar una pantalla de acceso denegado, sin inicializar el motor de visión

#### Scenario: Admin abre el harness por primera vez
- **WHEN** un admin con rol `admin_examenes` o `coordinador` navega a `/admin/detection-test`
- **THEN** el sistema SHALL mostrar la pantalla `AdminDetectionHarness` con el motor en estado `idle` (no inicializado) y un botón "Iniciar cámara" visible

#### Scenario: Admin inicia la cámara
- **WHEN** el admin hace clic en "Iniciar cámara"
- **THEN** el sistema SHALL solicitar permisos de cámara vía `getUserMedia`, inicializar `MediaPipeVisionEngine` y comenzar a procesar frames en el pipeline local

#### Scenario: Admin detiene el harness
- **WHEN** el admin hace clic en "Detener"
- **THEN** el sistema SHALL detener el loop de frames, llamar a `VisionEngine.dispose()` y liberar el stream de cámara

### Requirement: Panel de señales crudas en tiempo real
El sistema SHALL mostrar en la pantalla del harness, actualizándose por cada frame procesado, las señales crudas producidas por los detectores del motor: `face_count`, bounding boxes (x, y, width, height, confidence) de cada rostro, vector de gaze (x, y) cuando hay al menos un rostro, e indicación de disponibilidad de keypoints de pose.

#### Scenario: Frame con un solo rostro detectado
- **WHEN** el motor detecta `face_count = 1` en un frame
- **THEN** el panel de señales SHALL mostrar "1 rostro" con la bounding box (x, y, width, height, confidence) y el vector gaze en tiempo real

#### Scenario: Frame sin rostro
- **WHEN** el motor detecta `face_count = 0`
- **THEN** el panel SHALL mostrar "Sin rostro detectado" y ocultar los campos de gaze y bounding box

#### Scenario: Múltiples rostros en frame
- **WHEN** el motor detecta `face_count >= 2`
- **THEN** el panel SHALL mostrar todas las bounding boxes y resaltar visualmente la condición de múltiples rostros (borde o badge de alerta)

### Requirement: Panel de configuración de umbrales en tiempo real
El sistema SHALL exponer los parámetros de `TransitionConfig` (`face_absent_ms`, `multiple_faces_frames`, `gaze_deviation_threshold`, `gaze_sustained_ms`, `gaze_fixation_tolerance`) como controles editables en la UI del harness, aplicando los cambios al pipeline sin reiniciar el motor.

#### Scenario: Admin ajusta face_absent_ms
- **WHEN** el admin modifica el campo `face_absent_ms` a un valor válido (número positivo)
- **THEN** el sistema SHALL instanciar una nueva `StateTransitionRules` con el config actualizado y reemplazarla en el pipeline activo para el próximo frame, sin interrumpir el stream de cámara

#### Scenario: Admin ingresa un valor inválido en un umbral
- **WHEN** el admin ingresa un valor no numérico o negativo en un campo de `TransitionConfig`
- **THEN** el sistema SHALL mostrar un mensaje de error inline y mantener el valor anterior en el pipeline

### Requirement: Botón de reset de estado del pipeline
El sistema SHALL proveer un botón "Resetear estado" que reinicie la máquina de estados de `StateTransitionRules` (instancia nueva) sin detener el stream de cámara ni reinicializar el motor.

#### Scenario: Admin resetea el estado tras provocar un evento
- **WHEN** el admin hace clic en "Resetear estado"
- **THEN** el sistema SHALL reemplazar la instancia de `StateTransitionRules` por una nueva con el mismo config actual, limpiando contadores (ausencia, múltiples rostros, gaze) sin interrumpir el video
