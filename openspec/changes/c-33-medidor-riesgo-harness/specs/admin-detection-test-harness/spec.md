## MODIFIED Requirements

### Requirement: El harness es solo herramienta de diagnóstico admin
`AdminDetectionHarness` SHALL clearly communicate that it is a diagnostic tool only and does not produce exam evidence, regardless of whether the real engine is active. El widget de medidor de riesgo SHALL reforzar esta semántica: el score acumulado es solo referencial para diagnóstico y no implica ninguna sanción ni decisión.

#### Scenario: advertencia de herramienta diagnóstica siempre visible
- **WHEN** el harness está en cualquier estado (simulated, loading, real-active, error)
- **THEN** el header panel SHALL mostrar el banner diagnóstico de C-29, dejando claro que esta herramienta no genera evidencia real y es solo para uso admin

#### Scenario: widget de riesgo en contexto diagnóstico
- **WHEN** el widget de medidor de riesgo es visible
- **THEN** SHALL estar claramente enmarcado en la UI como parte del harness de diagnóstico, sin posibilidad de confusión con el score real de un alumno en examen

## ADDED Requirements

### Requirement: Integración del widget de riesgo en el layout del harness
El harness SHALL incluir el widget `harness-risk-meter` como `<Card>` dentro de su columna de controles/configuración, accesible sin scroll en resoluciones de escritorio estándar.

#### Scenario: widget visible durante una sesión activa
- **WHEN** el harness está en estado `running` y se emiten eventos
- **THEN** el widget de medidor SHALL estar visible y actualizado en tiempo real sin necesidad de scroll adicional

#### Scenario: widget visible en estado idle y stopped
- **WHEN** el harness está en estado `idle` o `stopped`
- **THEN** el widget SHALL ser visible (aunque el score sea 0 y la barra inactiva), permitiendo que el admin configure el umbral antes de iniciar

#### Scenario: reset de riesgo no afecta el estado del motor
- **WHEN** el admin presiona "Resetear riesgo" durante una sesión activa
- **THEN** el motor de visión, el pipeline y los detectores de contexto SHALL continuar funcionando sin interrupción
