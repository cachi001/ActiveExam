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
Los valores por defecto de `TransitionConfig` SHALL reflejar el rango alcanzable del vector gaze producido por `gazeFromIris()`. El vector gaze tiene magnitud práctica de 0.15–0.35 para una desviación lateral visible; los defaults SHALL permitir que una mirada de ~30 % de desviación sostenida 2.5 segundos dispare el evento. Estos umbrales SHALL poder **leerse desde la configuración persistida server-side** (`configuracion_sistema`): el `DEFAULT_CONFIG` del frontend SHALL actuar únicamente como baseline cuando la configuración efectiva aún no se cargó, y la configuración efectiva vigente SHALL prevalecer sobre las constantes hardcodeadas.

#### Scenario: umbral alcanzable con desviación lateral moderada
- **WHEN** el estudiante mira hacia un lado de forma sostenida (desviación de iris ≈ 30 % del semi-ancho del ojo)
- **THEN** la componente horizontal del vector gaze SHALL superar `gaze_deviation_threshold` (0.20) y, tras sostenerse `gaze_sustained_ms` (2500 ms) sin resetear el ancla por más de `gaze_fixation_tolerance` (0.25), el evento `mirada_desviada_sostenida` SHALL emitirse

#### Scenario: micro-movimientos oculares no disparan el evento
- **WHEN** el estudiante tiene micro-movimientos oculares involuntarios (magnitud < 0.15)
- **THEN** ninguna componente SHALL superar el umbral de su eje y NO SHALL emitirse ningún evento de mirada desviada

### Requirement: La desviación de mirada se evalúa por eje, con tolerancia vertical ampliada
La pantalla que el estudiante mira es un rectángulo ancho, no un punto: recorrerla con la vista desplaza el vector gaze, y leer un párrafo en su borde inferior supera `gaze_sustained_ms`. Evaluar la desviación como un radio (`hypot(x, y)` contra un umbral único) SHALL NO usarse, porque trata igual una mirada lateral fuera del monitor y una lectura dentro de él, y produce más falsos positivos cuanto más grande es la pantalla. Las reglas SHALL comparar cada componente contra el umbral de su eje: la horizontal contra `gaze_deviation_threshold` y la vertical contra ese mismo umbral multiplicado por un factor de tolerancia. El eje vertical SHALL conservar umbral propio y NO SHALL ignorarse, porque la consulta de apuntes sobre el escritorio cae en ese eje a un ángulo muy superior al del borde de la pantalla. El factor SHALL derivarse del umbral configurado y NO SHALL exponerse como parámetro independiente, para que la institución conserve un único control de sensibilidad.

#### Scenario: leer el borde inferior de la pantalla no es mirada desviada
- **WHEN** el estudiante sostiene la mirada en un desvío puramente vertical dentro del área de su pantalla (componente vertical bajo el umbral de su eje) durante más de `gaze_sustained_ms`
- **THEN** NO SHALL emitirse ningún evento de mirada desviada, aunque la magnitud del vector supere `gaze_deviation_threshold`

#### Scenario: consulta de apuntes sobre el escritorio sigue detectándose
- **WHEN** el estudiante sostiene la mirada muy por debajo de su pantalla (componente vertical por encima del umbral de su eje) durante más de `gaze_sustained_ms`
- **THEN** el evento `mirada_desviada_sostenida` SHALL emitirse con severidad media, sin sanción automática

#### Scenario: la tolerancia vertical acompaña a la sensibilidad configurada
- **WHEN** un `admin_sistema` endurece `gaze_deviation_threshold` en la configuración efectiva
- **THEN** el umbral vertical SHALL endurecerse en la misma proporción, sin requerir un campo de configuración adicional

#### Scenario: movimiento natural de cabeza no resetea el ancla
- **WHEN** el estudiante mantiene la mirada en una dirección pero tiene movimiento natural de cabeza (drift del vector ≤ 0.24)
- **THEN** el drift SHALL estar dentro de `gaze_fixation_tolerance` (0.25) y el contador de tiempo sostenido SHALL NO reiniciarse

#### Scenario: La config efectiva prevalece sobre el DEFAULT_CONFIG
- **WHEN** un `admin_sistema` edita los umbrales de detección y un consumidor carga la configuración efectiva
- **THEN** los umbrales aplicados SHALL ser los de la configuración persistida vigente, no los del `DEFAULT_CONFIG` hardcodeado

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

