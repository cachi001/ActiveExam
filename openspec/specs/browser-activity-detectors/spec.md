# browser-activity-detectors

## Purpose

Define los detectores de actividad de navegador y entorno que se ejecutan en el cliente (cambio o apertura de pestaña, salida de pantalla completa, copiar y pegar) y producen señales discretas para las reglas de transición. Son sensores no confiables (cliente) que alimentan el mismo `EventSink` que la visión y NUNCA emiten veredicto ni sanción: solo registran evidencia para la revisión humana posterior (L2.5, RN-EV-04).

## Requirements

### Requirement: Detección de cambio o apertura de pestaña
El cliente SHALL detectar mediante la Page Visibility API cuando la pestaña del examen deja de estar visible (el estudiante cambia o abre otra pestaña), produciendo una señal de contexto distinta de la pérdida de foco de ventana, que alimenta las reglas de transición. El detector SHALL ser inyectable (dependencia `doc`) para permitir pruebas sin un navegador real.

#### Scenario: La pestaña del examen deja de estar visible
- **WHEN** la pestaña del examen pasa a estado oculto (`visibilityState === "hidden"`)
- **THEN** el detector produce una señal de cambio de pestaña para las reglas de transición, diferenciada de la señal de pérdida de foco de ventana

#### Scenario: La pestaña vuelve a estar visible
- **WHEN** la pestaña del examen vuelve a estado visible
- **THEN** el detector deja de producir la señal de cambio de pestaña, sin emitir ninguna sanción

### Requirement: Detección de salida de pantalla completa
El cliente SHALL detectar mediante el evento `fullscreenchange` cuando el examen sale del modo de pantalla completa, produciendo una señal de salida de pantalla completa para las reglas de transición. El detector SHALL ser inyectable (dependencia `doc`) para pruebas sin navegador real.

#### Scenario: El estudiante sale de pantalla completa
- **WHEN** el documento del examen estaba en pantalla completa y deja de estarlo (no hay elemento en fullscreen)
- **THEN** el detector produce una señal de salida de pantalla completa para las reglas de transición

#### Scenario: El estudiante vuelve a entrar en pantalla completa
- **WHEN** el documento del examen vuelve a entrar en pantalla completa
- **THEN** el detector deja de producir la señal de salida, sin emitir ninguna sanción

### Requirement: Detección de copiar y pegar
El cliente SHALL detectar los eventos `copy` y `paste` sobre el documento del examen como señal de actividad de portapapeles, sin leer ni almacenar el contenido del portapapeles (privacidad; el contenido del cliente no es evidencia válida). El detector SHALL ser inyectable para pruebas sin navegador real.

#### Scenario: El estudiante pega contenido durante el examen
- **WHEN** ocurre un evento `paste` sobre el documento del examen
- **THEN** el detector produce una señal de actividad de portapapeles (acción `paste`) para las reglas de transición, sin capturar el contenido pegado

#### Scenario: El estudiante copia contenido durante el examen
- **WHEN** ocurre un evento `copy` sobre el documento del examen
- **THEN** el detector produce una señal de actividad de portapapeles (acción `copy`), sin capturar el contenido copiado

### Requirement: Las señales de navegador no producen sanciones
Los detectores de actividad de navegador SHALL producir únicamente señales para las reglas de transición; NUNCA SHALL emitir un veredicto, sanción o decisión disciplinaria (L2.5). La evidencia real se re-valida server-side.

#### Scenario: Actividad de navegador detectada
- **WHEN** cualquier detector de navegador produce una señal
- **THEN** el resultado es una señal o evento marcado como sospechoso para registro y revisión humana, y el sistema no aplica ninguna sanción automática
