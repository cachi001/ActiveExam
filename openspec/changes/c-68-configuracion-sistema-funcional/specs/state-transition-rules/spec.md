# state-transition-rules

## MODIFIED Requirements

### Requirement: DEFAULT_CONFIG con umbrales de gaze calibrados al rango real del vector iris
Los valores por defecto de `TransitionConfig` SHALL reflejar el rango alcanzable del vector gaze producido por `gazeFromIris()`. El vector gaze tiene magnitud práctica de 0.15–0.35 para una desviación lateral visible; los defaults SHALL permitir que una mirada de ~30 % de desviación sostenida 2.5 segundos dispare el evento. Estos umbrales SHALL poder **leerse desde la configuración persistida server-side** (`configuracion_sistema`): el `DEFAULT_CONFIG` del frontend SHALL actuar únicamente como baseline cuando la configuración efectiva aún no se cargó, y la configuración efectiva vigente SHALL prevalecer sobre las constantes hardcodeadas.

#### Scenario: umbral alcanzable con desviación lateral moderada
- **WHEN** el estudiante mira hacia un lado de forma sostenida (desviación de iris ≈ 30 % del semi-ancho del ojo)
- **THEN** la magnitud del vector gaze SHALL superar `gaze_deviation_threshold` (0.25) y — tras sostenerse `gaze_sustained_ms` (2500 ms) sin resetear el ancla por más de `gaze_fixation_tolerance` (0.25) — el evento `mirada_desviada_sostenida` SHALL emitirse

#### Scenario: micro-movimientos oculares no disparan el evento
- **WHEN** el estudiante tiene micro-movimientos oculares involuntarios (magnitud < 0.15)
- **THEN** la magnitud SHALL estar por debajo de `gaze_deviation_threshold` y NO SHALL emitirse ningún evento de mirada desviada

#### Scenario: movimiento natural de cabeza no resetea el ancla
- **WHEN** el estudiante mantiene la mirada en una dirección pero tiene movimiento natural de cabeza (drift del vector ≤ 0.24)
- **THEN** el drift SHALL estar dentro de `gaze_fixation_tolerance` (0.25) y el contador de tiempo sostenido SHALL NO reiniciarse

#### Scenario: La config efectiva prevalece sobre el DEFAULT_CONFIG
- **WHEN** un `admin_sistema` edita los umbrales de detección y un consumidor carga la configuración efectiva
- **THEN** los umbrales aplicados SHALL ser los de la configuración persistida vigente, no los del `DEFAULT_CONFIG` hardcodeado
