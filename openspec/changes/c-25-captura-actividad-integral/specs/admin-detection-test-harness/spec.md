# Spec delta — admin-detection-test-harness (C-23)

> El harness deja de inyectar `focus_lost/extra_monitor` fijos en `false` y cablea los detectores de contexto reales, sumando un panel de señales de entorno en vivo, para validar de forma integral visión + navegador.

## MODIFIED Requirements

### Requirement: Panel de señales crudas en tiempo real
El sistema SHALL mostrar en la pantalla del harness, actualizándose por cada frame procesado, las señales crudas de visión producidas por los detectores del motor (`face_count`, bounding boxes de cada rostro, vector de gaze cuando hay al menos un rostro, disponibilidad de keypoints de pose) Y las señales de entorno de navegador en vivo provenientes de los detectores de contexto reales (foco de ventana, visibilidad de pestaña, estado de pantalla completa, última actividad de copiar/pegar y disponibilidad/estado de monitores múltiples). El harness NO SHALL inyectar valores fijos de contexto: SHALL cablear los detectores de contexto reales.

#### Scenario: Frame con un solo rostro detectado
- **WHEN** el motor detecta `face_count = 1` en un frame
- **THEN** el panel de señales muestra "1 rostro" con la bounding box y el vector gaze en tiempo real

#### Scenario: El operador cambia de pestaña o pierde el foco
- **WHEN** durante la sesión de prueba la pestaña deja de estar visible o la ventana pierde el foco
- **THEN** el panel de señales de entorno refleja el cambio en vivo y el pipeline emite el evento correspondiente (`cambio_pestana` o `perdida_de_foco`) registrado en el log

#### Scenario: El operador sale de pantalla completa o pega contenido
- **WHEN** durante la sesión de prueba el operador sale de pantalla completa o ejecuta un paste
- **THEN** el panel de señales de entorno refleja la acción y el pipeline emite el evento `salida_pantalla_completa` o `copiar_pegar` registrado en el log

#### Scenario: Múltiples rostros en frame
- **WHEN** el motor detecta `face_count >= 2`
- **THEN** el panel muestra todas las bounding boxes y resalta la condición de múltiples rostros
