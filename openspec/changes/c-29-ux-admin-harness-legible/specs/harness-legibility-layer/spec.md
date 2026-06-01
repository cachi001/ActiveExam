## ADDED Requirements

### Requirement: Banner de simulación siempre visible
El harness de detección (`AdminDetectionHarness`) SHALL mostrar un banner prominente con fondo warning que diga "SEÑALES DE VISIÓN SIMULADAS — El motor MediaPipe está en modo demo y devuelve valores fijos. Las señales de navegador (pestaña, pantalla completa, portapapeles) SÍ son reales." Este banner SHALL estar posicionado antes del video y de los paneles de señales, y SHALL ser visible en todos los estados del harness (`idle`, `initializing`, `running`, `error`).

#### Scenario: Banner visible antes de iniciar cámara
- **WHEN** el admin accede a `/admin/detection-test` con `harnessState === 'idle'`
- **THEN** el banner de simulación es visible sin necesidad de hacer scroll

#### Scenario: Banner visible con harness activo
- **WHEN** el harness está corriendo (`harnessState === 'running'`) y se muestran señales
- **THEN** el banner de simulación sigue siendo visible en la misma vista

#### Scenario: Banner no bloquea la interacción
- **WHEN** el banner está visible
- **THEN** el admin puede iniciar la cámara y usar el harness normalmente sin descartar el banner

### Requirement: Panel de propósito del harness
El harness SHALL mostrar un panel informativo colapsable con el título "¿Para qué sirve esta prueba?" que explique en lenguaje no técnico: (1) el objetivo del harness, (2) las acciones que el admin debe realizar durante la prueba, (3) cuáles señales son reales y cuáles simuladas. Este panel SHALL usar el componente `<Term>` del glosario C-28 para los términos técnicos que aparezcan en el texto explicativo.

#### Scenario: Panel de propósito visible al cargar
- **WHEN** la pantalla del harness carga por primera vez
- **THEN** el panel de propósito está visible (puede estar colapsado por defecto pero su título es visible)

#### Scenario: Panel enumera acciones de prueba
- **WHEN** el admin expande el panel de propósito
- **THEN** ve al menos las siguientes acciones sugeridas: moverse frente a la cámara, tapar la cámara, cambiar de pestaña, pegar texto en el portapapeles, salir de pantalla completa

### Requirement: Señales de visión con interpretación en lenguaje claro
El panel de señales de visión SHALL presentar primero la interpretación en lenguaje claro antes de los datos técnicos crudos. Las tarjetas de interpretación SHALL mostrar:
- Rostros: "Se detectó 1 persona" / "No se detectó ninguna persona" / "Se detectaron N personas"
- Mirada: "Mirando hacia el frente" / "Mirando hacia un costado"
- Cuerpo: "Cuerpo presente" / "Cuerpo no detectado"

Cada tarjeta SHALL usar colores semánticos (success/warning/error) acorde al estado detectado, con etiqueta adicional `[SIMULADO]` en el título del panel.

#### Scenario: Tarjeta de rostros en estado normal
- **WHEN** `rawSignals.faceDetection.face_count === 1`
- **THEN** la tarjeta muestra "Se detectó 1 persona frente a la cámara" con tono success y badge `[SIMULADO]`

#### Scenario: Tarjeta de rostros en estado sin persona
- **WHEN** `rawSignals.faceDetection.face_count === 0`
- **THEN** la tarjeta muestra "No se detectó ninguna persona" con tono warning

#### Scenario: Tarjeta de mirada con vector disponible
- **WHEN** `rawSignals.faceMesh` tiene valores de gaze
- **THEN** la tarjeta muestra una interpretación de dirección de mirada en lenguaje natural

### Requirement: Datos técnicos crudos colapsables
Los datos técnicos crudos (coordenadas normalizadas de bounding boxes, vector gaze numérico, pose keypoints) SHALL estar ocultos por defecto bajo un accordion "Ver detalle técnico (coordenadas)" que el admin puede expandir opcionalmente. El accordion SHALL abrirse automáticamente si se detecta una anomalía (face_count !== 1 mientras el harness corre).

#### Scenario: Datos crudos ocultos por defecto en estado normal
- **WHEN** el harness está corriendo y `face_count === 1`
- **THEN** los bounding boxes, vector gaze y pose keypoints NO son visibles sin expandir el accordion

#### Scenario: Accordion se abre automáticamente en anomalía
- **WHEN** el harness está corriendo y `face_count !== 1`
- **THEN** el accordion de datos técnicos se abre automáticamente para facilitar el debugging

#### Scenario: Admin puede expandir accordion manualmente
- **WHEN** el admin hace clic en "Ver detalle técnico (coordenadas)"
- **THEN** los datos crudos (coordenadas, vectores) se muestran en formato mono como antes

### Requirement: Señales de entorno con descripción contextual
Cada señal de entorno (foco de ventana, pestaña, pantalla completa, portapapeles, monitor adicional) SHALL tener una descripción breve de qué detecta y por qué es relevante para el proctoring, visible en el panel de señales de entorno.

#### Scenario: Descripción visible en cada señal de entorno
- **WHEN** el panel "Señales de entorno" está visible (harness running)
- **THEN** cada señal muestra una línea descriptiva como "Detecta si el alumno abandonó la ventana del examen"

#### Scenario: Señales de entorno marcadas como REALES
- **WHEN** el panel "Señales de entorno" está visible
- **THEN** hay un indicador visible (badge o texto) que dice "Señal REAL del navegador" para distinguirlas de las señales de visión simuladas

### Requirement: Cadena de custodia colapsable en SessionDetail
En `SessionDetail.tsx`, la sección de "Cadena de custodia criptográfica" (4 pasos `CadenaPaso` con hashes largos) SHALL estar envuelta en un elemento colapsable. En pantallas anchas (≥1024px) SHALL estar expandida por defecto; en pantallas más angostas SHALL estar colapsada por defecto. Los valores de hash largos SHALL truncarse a los primeros 12 caracteres con un control "ver completo" inline para expandirlos.

#### Scenario: Sección colapsada en tablet/mobile
- **WHEN** el ancho de pantalla es menor a 1024px
- **THEN** la sección de cadena de custodia está colapsada y muestra solo su título

#### Scenario: Hash truncado con opción de expandir
- **WHEN** la sección de cadena de custodia está visible
- **THEN** los hashes muestran solo los primeros 12 caracteres seguidos de "..." y un botón "ver completo"

### Requirement: Respiro visual en tabla de eventos de Revisor
En `Revisor.tsx`, cada item de la lista de eventos SHALL tener padding interno `p-md` en lugar de `p-sm`, con separación visible entre items. Cuando hay 5 o más eventos del mismo tipo consecutivos, SHALL mostrarse agrupados con un contador "N veces" en lugar de N items repetidos.

#### Scenario: Eventos con mayor padding
- **WHEN** se renderiza la lista de eventos de una sesión en revisión
- **THEN** cada item tiene padding interno ≥ 12px (equivalente a `p-md`)

#### Scenario: Agrupación de eventos repetidos
- **WHEN** hay 5 o más eventos consecutivos del mismo tipo
- **THEN** se muestran agrupados como un solo item con badge de conteo "N veces"
