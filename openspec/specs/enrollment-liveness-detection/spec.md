# enrollment-liveness-detection Specification

## Purpose
TBD - created by archiving change c-34-biometria-perfil-funcional. Update Purpose after archive.
## Requirements
### Requirement: Motor real cargado lazy al iniciar captura
El sistema SHALL cargar `RealMediaPipeVisionEngine` mediante `enrollmentEngineLoader.ts` (dynamic import, singleton a nivel módulo) al iniciar el paso biométrico, de modo que `@mediapipe/tasks-vision` NO entre en el bundle inicial.

#### Scenario: Carga exitosa del motor
- **WHEN** el usuario hace clic en "Iniciar captura de referencia" por primera vez en la sesión
- **THEN** el sistema muestra un spinner "Preparando verificación…" mientras `loadEnrollmentEngine()` resuelve, y al resolverse pasa a la fase `capturando`

#### Scenario: Motor ya cacheado en sesión
- **WHEN** el usuario intenta una segunda captura en la misma sesión de página
- **THEN** el sistema reutiliza la instancia cacheada sin llamar `init()` nuevamente (latencia de inicio < 100ms)

#### Scenario: Fallo de carga del motor (WebGL ausente o modelo no encontrado)
- **WHEN** `loadEnrollmentEngine()` rechaza con un error
- **THEN** el sistema muestra un mensaje de error descriptivo y un botón "Continuar sin detección automática" que activa el modo fallback manual

### Requirement: Loop de detección frame-a-frame durante liveness activo
El sistema SHALL ejecutar un loop `requestAnimationFrame` mientras la fase sea `capturando`, procesando cada frame del video con `detectFaceMesh` y `detectFaces` del motor real, y evaluando los retos pendientes contra los thresholds definidos.

#### Scenario: Loop activo durante captura
- **WHEN** la fase es `capturando` y el motor está listo
- **THEN** el sistema llama `createImageBitmap(videoElement)` y `engine.detectFaceMesh(bitmap)` en cada frame, evaluando los retos contra los thresholds

#### Scenario: Loop cancelado al salir de la fase
- **WHEN** la fase cambia a `procesando`, `completado`, `error`, o el componente se desmonta
- **THEN** el sistema llama `cancelAnimationFrame(rafHandle)` deteniendo el loop

#### Scenario: Sin cara detectada en el frame
- **WHEN** `detectFaces` retorna `face_count === 0`
- **THEN** el sistema resetea todos los acumuladores de frames consecutivos sin marcar ningún reto como resuelto

### Requirement: Resolución de reto `girar_izquierda` por gaze real
El sistema SHALL marcar el reto `girar_izquierda` como resuelto cuando `gazeFromIris()` retorne `gaze.x < -0.25` durante al menos 3 frames consecutivos.

#### Scenario: Giro a la izquierda detectado
- **WHEN** el usuario gira la cabeza a su izquierda (gaze.x < -0.25) por 3 frames seguidos
- **THEN** el sistema marca el reto `girar_izquierda` como resuelto y lo muestra con check en la UI

#### Scenario: Giro parcial insuficiente
- **WHEN** el usuario gira levemente (gaze.x entre -0.10 y -0.25) o interrumpe el giro antes de 3 frames
- **THEN** el acumulador del reto se resetea y el reto no se marca como resuelto

### Requirement: Resolución de reto `girar_derecha` por gaze real
El sistema SHALL marcar el reto `girar_derecha` como resuelto cuando `gazeFromIris()` retorne `gaze.x > +0.25` durante al menos 3 frames consecutivos.

#### Scenario: Giro a la derecha detectado
- **WHEN** el usuario gira la cabeza a su derecha (gaze.x > +0.25) por 3 frames seguidos
- **THEN** el sistema marca el reto `girar_derecha` como resuelto

#### Scenario: Giro parcial insuficiente
- **WHEN** el usuario gira levemente (gaze.x entre +0.10 y +0.25) o interrumpe antes de 3 frames
- **THEN** el acumulador se resetea y el reto no se resuelve

### Requirement: Resolución de reto `parpadear` por cierre ocular real
El sistema SHALL marcar el reto `parpadear` como resuelto cuando la distancia vertical normalizada entre los landmarks superior (159) e inferior (145) del ojo izquierdo sea menor a `0.015` durante al menos 2 frames consecutivos.

#### Scenario: Parpadeo completo detectado
- **WHEN** el usuario cierra el ojo (distancia vertical landmark 159-145 < 0.015) por 2 frames seguidos
- **THEN** el sistema marca el reto `parpadear` como resuelto

#### Scenario: Parpadeo incompleto o guiño sin cierre total
- **WHEN** la distancia vertical es ≥ 0.015 (ojo entreabierto)
- **THEN** el acumulador se resetea y el reto no se resuelve

### Requirement: Resolución de reto `acercarse` por bounding box real
El sistema SHALL marcar el reto `acercarse` como resuelto cuando el bounding box del rostro detectado por `FaceDetector` tenga `bbox.width > 0.55` (normalizado al ancho del frame) durante al menos 3 frames consecutivos.

#### Scenario: Acercamiento suficiente detectado
- **WHEN** el usuario acerca el rostro a la cámara hasta que el bbox ocupa más del 55% del ancho del frame, por 3 frames seguidos
- **THEN** el sistema marca el reto `acercarse` como resuelto

#### Scenario: Rostro demasiado lejos
- **WHEN** el bbox.width ≤ 0.55
- **THEN** el acumulador se resetea y el reto no se resuelve

### Requirement: Resolución de reto `sonreír` por landmarks de boca reales
El sistema SHALL marcar el reto `sonreír` como resuelto cuando la distancia horizontal normalizada entre las comisuras de boca (landmarks 61 y 291) sea mayor a `0.12` durante al menos 3 frames consecutivos.

#### Scenario: Sonrisa detectada
- **WHEN** el usuario sonríe ampliamente (distancia horizontal comisuras > 0.12) por 3 frames seguidos
- **THEN** el sistema marca el reto `sonreír` como resuelto

#### Scenario: Expresión neutral insuficiente
- **WHEN** la distancia horizontal ≤ 0.12 (boca en reposo)
- **THEN** el acumulador se resetea y el reto no se resuelve

### Requirement: Embedding real derivado de landmarks
El sistema SHALL calcular el embedding usando `embeddingFromLandmarks(lastLandmarks)` (de `MediaPipeVisionEngine.ts`) con los landmarks del último frame del loop, reemplazando la generación con `Math.random`.

#### Scenario: Embedding calculado con landmarks reales
- **WHEN** todos los retos están resueltos y se ejecuta `procesarCaptura()`
- **THEN** el campo `embedding` enviado a `api.guardarReferenciaBiometrica` es el vector determinista de `embeddingFromLandmarks`, con dimensionalidad igual a `3 × nro_de_landmarks`

#### Scenario: Sin landmarks disponibles (cara no detectada al procesar)
- **WHEN** `lastLandmarks` está vacío al momento de procesar
- **THEN** el sistema retorna al estado `capturando` con un mensaje "No se detectó tu cara, intentá de nuevo" en lugar de generar un embedding vacío

### Requirement: Fallback manual cuando el motor no está disponible
El sistema SHALL mostrar botones de resolución manual de retos (el comportamiento previo) únicamente cuando el motor no pudo cargar, etiquetados claramente como "Modo de prueba sin detección automática".

#### Scenario: Fallback activado por fallo de motor
- **WHEN** `loadEnrollmentEngine()` falla y el usuario elige "Continuar sin detección automática"
- **THEN** el sistema muestra botones por reto para resolución manual, con un banner que indica "El motor de visión no está disponible en este entorno"

#### Scenario: Motor disponible — sin botones manuales
- **WHEN** el motor carga correctamente
- **THEN** NO hay botones de resolución manual visibles; los retos se resuelven solo por detección

### Requirement: Disposal del motor al desmontar el componente
El sistema SHALL llamar `disposeEnrollmentEngine()` en el cleanup del `useEffect` que gestiona el ciclo de vida del motor, para liberar los recursos WASM al navegar fuera del perfil.

#### Scenario: Cleanup al navegar fuera
- **WHEN** el componente `EnrollmentBiometricStep` se desmonta (usuario navega a otra pantalla)
- **THEN** el sistema cancela el RAF loop y llama `disposeEnrollmentEngine()` liberando el singleton

