# window-management-permission-flow Specification

## Purpose
TBD - created by archiving change c-32-harness-motor-cache-ux. Update Purpose after archive.
## Requirements
### Requirement: Tipo ScreenPermissionResult para resultado de solicitud de permiso
`contextDetectors.ts` SHALL export a discriminated union type `ScreenPermissionResult` describing the three possible outcomes of requesting the `window-management` permission.

#### Scenario: tipo exportado con tres variantes
- **WHEN** `ScreenPermissionResult` is imported
- **THEN** it SHALL have exactly three variants: `{ status: 'unsupported' }`, `{ status: 'denied' }`, and `{ status: 'granted'; extra_monitor: boolean }`

### Requirement: Función requestAndDetectExtraMonitor
`contextDetectors.ts` SHALL export `requestAndDetectExtraMonitor(): Promise<ScreenPermissionResult>` that explicitly requests the `window-management` permission via a user gesture, detects browser support, and returns the appropriate result variant.

#### Scenario: navegador no soporta la API
- **WHEN** `requestAndDetectExtraMonitor()` is called in a browser where `window.getScreenDetails` does not exist
- **THEN** it SHALL return `{ status: 'unsupported' }` without throwing

#### Scenario: usuario deniega el permiso
- **WHEN** `requestAndDetectExtraMonitor()` is called and the user dismisses the permission prompt or the browser throws a `NotAllowedError`
- **THEN** it SHALL return `{ status: 'denied' }` without throwing

#### Scenario: usuario concede el permiso — una pantalla
- **WHEN** `requestAndDetectExtraMonitor()` is called, the user grants permission, and only one screen is detected
- **THEN** it SHALL return `{ status: 'granted', extra_monitor: false }`

#### Scenario: usuario concede el permiso — múltiples pantallas
- **WHEN** `requestAndDetectExtraMonitor()` is called, the user grants permission, and two or more screens are detected
- **THEN** it SHALL return `{ status: 'granted', extra_monitor: true }`

#### Scenario: función detectExtraMonitor existente permanece sin cambios
- **WHEN** `detectExtraMonitor(provider?)` is called (existing passive API)
- **THEN** its behavior SHALL be identical to the C-25 specification: returns `ContextSignal | null` without requesting any new permissions

### Requirement: UX del flujo de permiso en el harness
`AdminDetectionHarness` SHALL present a dedicated UI card for multi-monitor detection that guides the user through the permission flow with clear messaging for each state.

#### Scenario: navegador no soporta la API — mensaje explicativo
- **WHEN** the harness starts and `window.getScreenDetails` is not available
- **THEN** the monitor card SHALL display an informational message explaining that multi-monitor detection requires Chrome or Edge over HTTPS
- **AND** no permission request button SHALL be shown

#### Scenario: permiso no solicitado aún — botón visible
- **WHEN** the harness is running and the monitor permission state is `'idle'`
- **THEN** the monitor card SHALL show a button labelled "Detectar pantallas" (or equivalent)
- **AND** the card SHALL include a brief explanation: "Para detectar si hay más de un monitor conectado, el navegador necesita tu permiso."

#### Scenario: click en "Detectar pantallas" solicita el permiso
- **WHEN** the user clicks the "Detectar pantallas" button
- **THEN** the browser permission prompt SHALL be triggered (via `requestAndDetectExtraMonitor()`)
- **AND** the button SHALL be disabled (or a spinner shown) while the prompt is pending

#### Scenario: permiso denegado — botón de reintento
- **WHEN** the permission request returns `{ status: 'denied' }`
- **THEN** the monitor card SHALL display "Permiso denegado." and a "Reintentar" button
- **AND** clicking "Reintentar" SHALL call `requestAndDetectExtraMonitor()` again

#### Scenario: permiso concedido — señal activa
- **WHEN** the permission request returns `{ status: 'granted', extra_monitor: boolean }`
- **THEN** the monitor card SHALL display the detected value (extra monitor present: yes/no) using the same visual style as other environment signal cards
- **AND** the passive polling loop (existing `pollMonitor`) SHALL take over for subsequent updates without re-requesting permission

