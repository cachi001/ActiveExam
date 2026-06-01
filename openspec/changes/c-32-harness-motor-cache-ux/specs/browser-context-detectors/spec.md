## MODIFIED Requirements

### Requirement: Detección de monitores múltiples
El cliente SHALL detectar la presencia de monitores adicionales mediante la API de pantallas donde el navegador lo permita y SHALL cablear esa señal al pipeline de detección tanto en el flujo del alumno como en la página de testeo, dejando de inyectar un valor fijo. Donde la API no esté disponible o el permiso sea denegado, la señal SHALL degradar a "no determinable" sin abortar el pipeline.

#### Scenario: Monitor adicional detectado donde el navegador lo permite
- **WHEN** la API de pantallas está disponible y se detecta un monitor adicional
- **THEN** el detector produce la señal de "monitor adicional", que el pipeline consume para emitir el evento `monitor_adicional`

#### Scenario: API de pantallas no disponible
- **WHEN** la API de pantallas no está disponible o el permiso es denegado
- **THEN** la señal de monitor se considera "no determinable" y el pipeline continúa sin emitir falsos positivos ni abortar

## ADDED Requirements

### Requirement: Tipo ScreenPermissionResult para solicitud de permiso explícita
`contextDetectors.ts` SHALL export the discriminated union type `ScreenPermissionResult` with variants: `{ status: 'unsupported' }`, `{ status: 'denied' }`, and `{ status: 'granted'; extra_monitor: boolean }`.

#### Scenario: tipo con tres variantes discriminadas
- **WHEN** `ScreenPermissionResult` is imported from `contextDetectors`
- **THEN** it SHALL be usable as a discriminated union on the `status` field covering all three cases

### Requirement: Función requestAndDetectExtraMonitor para solicitar permiso con gesto
`contextDetectors.ts` SHALL export `requestAndDetectExtraMonitor(): Promise<ScreenPermissionResult>` that explicitly calls `window.getScreenDetails()` as a user gesture, detecting browser support and permission outcome without throwing.

#### Scenario: navegador no soporta la API
- **WHEN** `requestAndDetectExtraMonitor()` is called in a browser where `window.getScreenDetails` does not exist
- **THEN** it SHALL return `{ status: 'unsupported' }` without throwing

#### Scenario: usuario deniega el permiso
- **WHEN** `requestAndDetectExtraMonitor()` is called and the user dismisses the permission prompt or the browser rejects with `NotAllowedError`
- **THEN** it SHALL return `{ status: 'denied' }` without throwing

#### Scenario: usuario concede — una pantalla
- **WHEN** `requestAndDetectExtraMonitor()` is called and only one screen is detected
- **THEN** it SHALL return `{ status: 'granted', extra_monitor: false }`

#### Scenario: usuario concede — múltiples pantallas
- **WHEN** `requestAndDetectExtraMonitor()` is called and two or more screens are detected
- **THEN** it SHALL return `{ status: 'granted', extra_monitor: true }`

#### Scenario: detectExtraMonitor existente no se modifica
- **WHEN** `detectExtraMonitor(provider?)` is called (the passive polling function from C-25)
- **THEN** its behavior SHALL be unchanged: it accepts an optional `ScreenDetailsProvider` and returns `ContextSignal | null` without any permission side-effects
