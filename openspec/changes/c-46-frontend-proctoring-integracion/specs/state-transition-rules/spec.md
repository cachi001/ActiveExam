## MODIFIED Requirements

### Requirement: DEFAULT_CONFIG con umbrales calibrados para MediaPipe real
El `DEFAULT_CONFIG` de `StateTransitionRules` SHALL usar los siguientes valores ajustados para reducir falsos positivos observados con el motor MediaPipe real en el harness: `gaze_deviation_threshold: 0.20` (era 0.15 — aumentado para mirada), `face_absent_ms: 3000` (era 2000ms — más margen antes de disparar "rostro ausente"). Todos los demás valores del `DEFAULT_CONFIG` se preservan sin cambio. Los valores siguen siendo sobreescribibles por UI en el harness.

#### Scenario: DEFAULT_CONFIG tiene gaze_deviation_threshold de 0.20
- **WHEN** se instancia `StateTransitionRules` sin configuración explícita
- **THEN** `DEFAULT_CONFIG.gaze_deviation_threshold === 0.20`

#### Scenario: DEFAULT_CONFIG tiene face_absent_ms de 3000
- **WHEN** se instancia `StateTransitionRules` sin configuración explícita
- **THEN** `DEFAULT_CONFIG.face_absent_ms === 3000`

#### Scenario: Valores sobreescribibles desde la UI del harness
- **WHEN** el usuario modifica `gaze_deviation_threshold` en el panel de configuración del harness
- **THEN** la instancia de `StateTransitionRules` usa el valor ingresado por el usuario, no el DEFAULT_CONFIG
