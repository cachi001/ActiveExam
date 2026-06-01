# Spec delta — browser-context-detectors (C-11)

> Cablea el detector de monitores múltiples al flujo de producción (deja de estar hardcodeado) e incorpora los nuevos detectores de entorno bajo la misma abstracción inyectable.

## MODIFIED Requirements

### Requirement: Detección de monitores múltiples
El cliente SHALL detectar la presencia de monitores adicionales mediante la API de pantallas donde el navegador lo permita y SHALL cablear esa señal al pipeline de detección tanto en el flujo del alumno como en la página de testeo, dejando de inyectar un valor fijo. Donde la API no esté disponible o el permiso sea denegado, la señal SHALL degradar a "no determinable" sin abortar el pipeline.

#### Scenario: Monitor adicional detectado donde el navegador lo permite
- **WHEN** la API de pantallas está disponible y se detecta un monitor adicional
- **THEN** el detector produce la señal de "monitor adicional", que el pipeline consume para emitir el evento `monitor_adicional`

#### Scenario: API de pantallas no disponible
- **WHEN** la API de pantallas no está disponible o el permiso es denegado
- **THEN** la señal de monitor se considera "no determinable" y el pipeline continúa sin emitir falsos positivos ni abortar
