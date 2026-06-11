# enrollment-fullscreen-mobile Specification

## Purpose
TBD - created by archiving change c-34-biometria-perfil-funcional. Update Purpose after archive.
## Requirements
### Requirement: Detección de dispositivo móvil o pantalla pequeña
El sistema SHALL detectar si el dispositivo es móvil o táctil usando `window.innerWidth < 768 || 'ontouchstart' in window || navigator.maxTouchPoints > 0` para decidir si activar el modo fullscreen al iniciar la captura.

#### Scenario: Dispositivo móvil detectado
- **WHEN** el usuario accede al enrollment en un smartphone o tablet (touch device o ancho < 768px)
- **THEN** el sistema activa el modo fullscreen al hacer clic en "Iniciar captura de referencia"

#### Scenario: Dispositivo desktop
- **WHEN** el usuario accede en un desktop sin touch y ancho ≥ 768px
- **THEN** el sistema NO activa fullscreen al iniciar; la captura corre en el layout normal de la página

### Requirement: Pantalla completa al iniciar captura en móvil (Fullscreen API)
El sistema SHALL llamar `containerRef.current.requestFullscreen()` sobre el contenedor de captura al iniciar la fase `capturando` en dispositivos móviles. Si la API no está disponible o rechaza, SHALL activar el fallback CSS.

#### Scenario: requestFullscreen exitoso
- **WHEN** el usuario en móvil inicia la captura y el browser soporta `requestFullscreen` en elementos div
- **THEN** el contenedor de captura ocupa toda la pantalla, ocultando la barra de navegación del browser

#### Scenario: requestFullscreen no disponible (iOS Safari browser)
- **WHEN** `element.requestFullscreen` no existe o la promesa rechaza (iOS Safari no-PWA)
- **THEN** el sistema activa el fallback CSS (`fullscreenFallback = true`) sin lanzar un error visible al usuario

#### Scenario: Usuario sale de fullscreen con botón nativo del browser
- **WHEN** el usuario presiona el botón nativo de salida de fullscreen del browser mientras está en fase `capturando`
- **THEN** el listener `document.fullscreenchange` detecta el cambio y sincroniza el estado interno sin interrumpir la detección

### Requirement: Fallback CSS fullscreen-like cuando la API no está disponible
El sistema SHALL aplicar clases `fixed inset-0 z-50 bg-black` al contenedor de captura cuando `fullscreenFallback` es `true`, creando una experiencia visual idéntica a la pantalla completa nativa.

#### Scenario: Fallback activo en iOS Safari
- **WHEN** `requestFullscreen` falla y se activa `fullscreenFallback`
- **THEN** el contenedor de captura ocupa toda la pantalla con fondo negro, el visor de cámara y los retos son visibles en layout de pantalla completa, y el resto de la página queda oculta detrás

#### Scenario: Botón de cancelar accesible en fullscreen-like
- **WHEN** el modo `fullscreenFallback` está activo
- **THEN** el botón "Cancelar" es visible y funcional dentro del contenedor fixed, permitiendo salir sin bloquear al usuario

### Requirement: Salida de fullscreen al completar o cancelar
El sistema SHALL llamar `document.exitFullscreen?.()` y desactivar `fullscreenFallback` cuando la captura se completa exitosamente o el usuario cancela.

#### Scenario: Salida automática al completar captura
- **WHEN** la fase cambia a `completado`
- **THEN** el sistema llama `document.exitFullscreen?.()` (si estaba en fullscreen nativo) y setea `fullscreenFallback` a `false`, volviendo al layout normal de la página

#### Scenario: Salida por cancelar
- **WHEN** el usuario presiona el botón "Cancelar" durante la fase `capturando`
- **THEN** el sistema sale de fullscreen (nativo o fallback), detiene el RAF loop, y vuelve a la fase `instrucciones`

### Requirement: Layout optimizado para pantalla completa durante liveness activo
El sistema SHALL adaptar el layout del contenedor de captura en modo fullscreen/fallback para maximizar el uso de la pantalla: visor de cámara centrado y ampliado, lista de retos visible debajo sin scroll, con fondo oscuro para enfocar la atención.

#### Scenario: Layout fullscreen inmersivo
- **WHEN** el modo fullscreen (nativo o fallback) está activo
- **THEN** el visor de cámara ocupa la mayor parte de la altura de la pantalla, los retos son visibles en la parte inferior sin necesidad de scroll, y el fondo es oscuro (bg-black o bg-inverse-surface)

#### Scenario: Indicador de cámara activa visible en fullscreen
- **WHEN** el modo fullscreen está activo y la cámara está encendida
- **THEN** el indicador "CÁMARA" (punto rojo + label) es visible sobre el visor de cámara

