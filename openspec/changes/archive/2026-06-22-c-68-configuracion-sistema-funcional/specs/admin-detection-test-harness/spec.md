# admin-detection-test-harness

## ADDED Requirements

### Requirement: El harness carga la configuración efectiva como baseline
TEST DETECCIÓN SHALL cargar la configuración efectiva real (`GET /api/v1/config/effective`) como baseline de sus umbrales y pesos, en lugar de las constantes `DEFAULT_CONFIG` hardcodeadas. El harness SHALL conservar su naturaleza air-gapped para la **captura** (no envía eventos al backend), pero la **lectura** de configuración SHALL provenir del servidor para que "TEST DETECCIÓN use la configuración actualizada".

#### Scenario: El harness refleja una edición de configuración
- **WHEN** un `admin_sistema` edita un umbral y luego abre TEST DETECCIÓN
- **THEN** el harness SHALL usar el umbral editado como baseline (cargado desde la config efectiva), no la constante hardcodeada

#### Scenario: La captura sigue siendo air-gapped
- **WHEN** TEST DETECCIÓN procesa frames de la cámara
- **THEN** los eventos de detección SHALL permanecer locales (sin envío al backend), conservando el aislamiento de diagnóstico
