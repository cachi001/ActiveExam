## MODIFIED Requirements

### Requirement: El harness es solo herramienta de diagnóstico admin
`AdminDetectionHarness` SHALL clearly communicate that it is a diagnostic tool only and does not produce exam evidence, regardless of whether the real engine is active.

#### Scenario: advertencia de herramienta diagnóstica siempre visible
- **WHEN** the harness is in any state (simulated, loading, real-active, error)
- **THEN** the harness header panel SHALL display the diagnostic purpose statement from C-29, making clear this tool does not generate exam evidence and is for admin use only

## ADDED Requirements

### Requirement: El mesh completo está activo por defecto al cargar el harness
El harness de detección SHALL inicializar `showFullMesh` en `true`, de forma que la pantalla `/admin/detection-test` muestre los 468 landmarks de Face Mesh desde la primera carga sin intervención del usuario.

#### Scenario: Mesh de 468 puntos visible al cargar
- **WHEN** el administrador navega a `/admin/detection-test`
- **THEN** el overlay SHALL mostrar los 468 landmarks de Face Mesh inmediatamente al detectar un rostro, sin necesidad de activar el toggle manualmente

#### Scenario: Toggle de mesh sigue funcionando
- **WHEN** el mesh completo está activo y el administrador desactiva el toggle `showFullMesh`
- **THEN** el overlay SHALL dejar de renderizar los 468 landmarks y mostrar solo el punto central
- **WHEN** el administrador reactiva el toggle
- **THEN** los 468 landmarks SHALL volver a renderizarse
