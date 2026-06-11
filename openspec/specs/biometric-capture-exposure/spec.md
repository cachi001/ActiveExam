# biometric-capture-exposure Specification

## Purpose
TBD - created by archiving change c-65-fixes-captura-liveness-biometrica. Update Purpose after archive.
## Requirements
### Requirement: La captura solicita exposición real al sensor (best-effort)

Al iniciar la cámara, el sistema SHALL intentar mejorar la exposición del sensor vía `MediaStreamTrack.applyConstraints` (por ejemplo `exposureMode`/`brightness` u otras advanced constraints soportadas), de forma best-effort. Si el dispositivo o navegador no soporta la constraint, el sistema SHALL continuar sin error (fallback silencioso) y mantener la guía de encuadre.

El sistema SHALL conservar la advertencia `poca_luz` existente como guía al alumno, independientemente de si la constraint de exposición se aplicó.

#### Scenario: Dispositivo soporta exposición
- **WHEN** la cámara soporta la constraint de exposición/brillo
- **THEN** el sistema aplica la constraint y la imagen del sensor mejora su exposición

#### Scenario: Dispositivo no soporta exposición
- **WHEN** `applyConstraints` rechaza o la constraint no está soportada
- **THEN** el sistema continúa sin lanzar error y sigue mostrando la guía `poca_luz` cuando corresponde

### Requirement: El frame de referencia persistido nunca se post-procesa

El frame que se entrega para el cómputo del embedding / la evidencia (`bestReferenceFrameRef`) SHALL tomarse del elemento `<video>` crudo, sin aplicar filtros de software, ganancia, gamma ni corrección de brillo por post-proceso. Cualquier mejora visual de brillo destinada a comodidad del alumno SHALL aplicarse únicamente a la PRESENTACIÓN (p. ej. filtro CSS sobre el `<video>`) y NO SHALL afectar el frame capturado a canvas.

Esto preserva la regla de cliente = sensor no confiable: la referencia persistida es la lectura real, re-inferible y firmable server-side.

#### Scenario: Frame guardado es la lectura cruda
- **WHEN** se captura el frame de referencia durante el baseline
- **THEN** el frame proviene de `drawImage(video, …)` sobre el video crudo, sin post-proceso de brillo

#### Scenario: Mejora de preview no contamina la evidencia
- **WHEN** se aplica un filtro CSS de brillo al `<video>` para comodidad visual
- **THEN** el frame dibujado al canvas para el embedding NO refleja ese filtro

