# virtual-camera-detection Specification

## Purpose
TBD - created by archiving change c-09-biometria-liveness. Update Purpose after archive.
## Requirements
### Requirement: Detección de cámara virtual e inyección de pipeline
El sistema SHALL aplicar en el cliente una heurística de integridad para detectar el uso de una cámara virtual o la inyección de video sintético en el flujo de captura, y SHALL reportar esa señal al backend como parte de los datos del intento (DD-18).

#### Scenario: Cámara virtual detectada se reporta al backend
- **WHEN** la heurística de integridad detecta una cámara virtual o inyección de pipeline durante la captura
- **THEN** el sistema reporta la señal de cámara virtual al backend junto con el intento de verificación

#### Scenario: La señal de cámara virtual es una capa, no el veredicto único
- **WHEN** se reporta una señal de cámara virtual
- **THEN** el sistema la trata como una de las capas de defensa, sin que sustituya la re-inferencia server-side ni la decisión humana

