# Spec — browser-context-detectors

> Detectores de contexto del navegador: pestaña activa, foco de ventana y monitores múltiples (RN-EV-04, US-006, Flujo 3).

## ADDED Requirements

### Requirement: Detección de cambio de pestaña y pérdida de foco
El cliente SHALL detectar el cambio de pestaña activa y la pérdida de foco de la ventana mediante los eventos de visibilidad/foco del navegador, como señales que alimentan las reglas de transición.

#### Scenario: Pérdida de foco produce una señal de contexto
- **WHEN** la ventana del examen pierde el foco o la pestaña deja de estar activa
- **THEN** el detector produce una señal de cambio de pestaña / pérdida de foco para las reglas de transición

### Requirement: Detección de monitores múltiples
El cliente SHALL detectar la presencia de monitores adicionales mediante la API de pantallas donde el navegador lo permita, como señal de severidad potencialmente alta.

#### Scenario: Monitor adicional detectado donde el navegador lo permite
- **WHEN** la API de pantallas está disponible y se detecta un monitor adicional
- **THEN** el detector produce la señal de "monitor adicional" para las reglas de transición
