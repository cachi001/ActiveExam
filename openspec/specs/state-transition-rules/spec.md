# state-transition-rules

## Purpose

Define las reglas puras de transición que convierten señales del frame (mirada, pose, actividad de navegador) en **eventos discretos** con severidad. Garantiza la regla dura L2.5: ninguna transición deriva en sanción automática — solo flaggea evidencia para revisión humana posterior.
## Requirements
### Requirement: Transiciones de contexto de navegador
Las reglas de transición SHALL convertir las señales de contexto de navegador en eventos discretos con severidad: pérdida de foco de ventana → `perdida_de_foco` (baja), monitor adicional → `monitor_adicional` (alta), cambio o apertura de pestaña → `cambio_pestana` (media), salida de pantalla completa → `salida_pantalla_completa` (media) y actividad de copiar/pegar → `copiar_pegar` (media). Los eventos de navegador son discretos e instantáneos: se emiten en el frame en que la señal está presente y SHALL aplicar de-duplicación básica para no re-emitir el mismo estado de forma repetida mientras la señal persiste. NINGUNA transición SHALL derivar una sanción automática.

#### Scenario: Pérdida de foco de ventana
- **WHEN** la señal `focus_lost` está presente en el frame
- **THEN** las reglas emiten un evento `perdida_de_foco` de severidad baja, sin sanción

#### Scenario: Cambio o apertura de pestaña
- **WHEN** la señal de cambio de pestaña está presente en el frame
- **THEN** las reglas emiten un evento `cambio_pestana` de severidad media, distinto de `perdida_de_foco`, sin sanción

#### Scenario: Salida de pantalla completa
- **WHEN** la señal de salida de pantalla completa está presente en el frame
- **THEN** las reglas emiten un evento `salida_pantalla_completa` de severidad media, y no lo re-emiten hasta que el examen vuelva a entrar y salir de pantalla completa

#### Scenario: Copiar o pegar
- **WHEN** la señal de actividad de portapapeles (copy/paste) está presente en el frame
- **THEN** las reglas emiten un evento `copiar_pegar` de severidad media, sin capturar el contenido del portapapeles y sin sanción

#### Scenario: Monitor adicional
- **WHEN** la señal `extra_monitor` está presente en el frame
- **THEN** las reglas emiten un evento `monitor_adicional` de severidad alta, sin sanción

### Requirement: DEFAULT_CONFIG con umbrales de gaze calibrados al rango real del vector iris
Los valores por defecto de `TransitionConfig` SHALL reflejar el rango alcanzable del vector gaze producido por `gazeFromIris()`. El vector gaze tiene magnitud práctica de 0.15–0.35 para una desviación lateral visible; los defaults SHALL permitir que una mirada de ~30 % de desviación sostenida 2.5 segundos dispare el evento.

#### Scenario: umbral alcanzable con desviación lateral moderada
- **WHEN** el estudiante mira hacia un lado de forma sostenida (desviación de iris ≈ 30 % del semi-ancho del ojo)
- **THEN** la magnitud del vector gaze SHALL superar `gaze_deviation_threshold` (0.25) y — tras sostenerse `gaze_sustained_ms` (2500 ms) sin resetear el ancla por más de `gaze_fixation_tolerance` (0.25) — el evento `mirada_desviada_sostenida` SHALL emitirse

#### Scenario: micro-movimientos oculares no disparan el evento
- **WHEN** el estudiante tiene micro-movimientos oculares involuntarios (magnitud < 0.15)
- **THEN** la magnitud SHALL estar por debajo de `gaze_deviation_threshold` y NO SHALL emitirse ningún evento de mirada desviada

#### Scenario: movimiento natural de cabeza no resetea el ancla
- **WHEN** el estudiante mantiene la mirada en una dirección pero tiene movimiento natural de cabeza (drift del vector ≤ 0.24)
- **THEN** el drift SHALL estar dentro de `gaze_fixation_tolerance` (0.25) y el contador de tiempo sostenido SHALL NO reiniciarse

### Requirement: FrameSignals acepta head_yaw_deg como señal complementaria de gaze
`FrameSignals` SHALL aceptar el campo opcional `head_yaw_deg?: number` (grados, 0 = frontal, positivo = derecha, negativo = izquierda). Cuando el campo está presente, `evalGaze()` SHALL considerarlo como señal adicional de desviación: si `|head_yaw_deg| > HEAD_YAW_THRESHOLD_DEG` (20°) la condición de gaze desviado SHALL activarse incluso si la magnitud del vector iris está por debajo del umbral.

#### Scenario: head yaw > 20° activa la condición de gaze desviado
- **WHEN** `head_yaw_deg` es ±25 (giro de cabeza de 25°) y la magnitud del iris es 0.10 (debajo del umbral)
- **THEN** `evalGaze()` SHALL considerar la mirada como desviada e iniciar el contador de tiempo sostenido

#### Scenario: ausencia de head_yaw_deg no cambia el comportamiento
- **WHEN** `FrameSignals.head_yaw_deg` no está definido (undefined)
- **THEN** `evalGaze()` SHALL evaluar la desviación únicamente con la magnitud del vector gaze (comportamiento retrocompatible con C-11/C-25)

#### Scenario: head yaw dentro del rango frontal no activa la condición
- **WHEN** `head_yaw_deg` es ±10 (giro leve de cabeza)
- **THEN** la condición de gaze desviado por yaw SHALL NOT activarse (por debajo de `HEAD_YAW_THRESHOLD_DEG`)

