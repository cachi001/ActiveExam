## ADDED Requirements

### Requirement: El registro de sesión es un expediente revisable sin video

El sistema SHALL exponer, para cada sesión de proctoring, un **expediente revisable** compuesto de evidencia discreta — screenshots, chat proctor↔alumno, anotaciones del proctor y eventos discretos. El expediente SHALL NOT contener ni referenciar grabación de video continuo (RN-CC-01/RN-CO-03): "registro de sesión" NO es video. El contenido SHALL ser coherente con el tipo de sesión: una sesión de **examen** incluye screenshots, chat, anotaciones y eventos; una sesión de **test** incluye screenshots, eventos y métricas (statcards).

#### Scenario: Expediente de una sesión de examen

- **WHEN** un revisor abre el expediente de una sesión de examen
- **THEN** ve los screenshots, el chat con el proctor, las anotaciones del proctor y los eventos discretos de esa sesión

#### Scenario: Expediente de una sesión de test

- **WHEN** un revisor abre el expediente de una sesión de test
- **THEN** ve los screenshots, los eventos y las métricas de la sesión, sin exigir chat ni anotaciones si no aplican

#### Scenario: El expediente no ofrece video

- **WHEN** se recorre cualquier vista del expediente de sesión
- **THEN** no existe reproducción ni referencia a grabación de video continuo de la sesión

### Requirement: Todos los eventos discretos se listan; el evento es la evidencia

La UI del expediente SHALL listar todos los eventos discretos de la sesión sin ocultar ninguno por carecer de captura de cámara. Cada tipo de evento (`copiar_pegar`, `cambio_pestana`, `perdida_de_foco`, `monitor_adicional`, `salida_pantalla_completa`, `corte_conectividad_prolongado`, `rostro_ausente`, `multiples_rostros`, `mirada_desviada_sostenida`) es una anomalía discreta cuyo solo acontecimiento constituye la evidencia: el sistema SHALL NOT suprimir un evento por no tener screenshot asociado.

#### Scenario: Evento sin captura de cámara se lista igual

- **WHEN** una sesión tiene un evento `copiar_pegar` sin screenshot de cámara asociado
- **THEN** ese evento aparece en la lista del expediente, porque el hecho de haber pegado es en sí la evidencia

#### Scenario: Ningún tipo de evento se oculta por falta de captura

- **WHEN** se listan los eventos de una sesión
- **THEN** los eventos de foco, pestaña, monitor y conectividad aparecen aunque no tengan imagen adjunta

### Requirement: El conteo de rostros cliente/servidor se muestra solo con discrepancia y captura

El bloque de reconciliación del conteo de rostros (navegador vs. servidor) de una tarjeta de evento SHALL mostrarse únicamente cuando el conteo del cliente difiere del conteo del servidor (`face_count_cliente ≠ face_count_servidor`) **y** existe una captura asociada que permite inspeccionar la discrepancia. Cuando cliente y servidor coinciden, o cuando no hay captura, el bloque SHALL ocultarse por no aportar señal revisable. Esto SHALL ser un cambio de presentación: el conteo crudo de cliente y servidor SHALL conservarse íntegro server-side (regla dura #6).

#### Scenario: Discrepancia con captura se muestra

- **WHEN** un evento tiene `face_count_cliente = 2`, `face_count_servidor = 1` y una captura asociada
- **THEN** el bloque de conteo cliente/servidor se muestra, para que el revisor inspeccione la imagen

#### Scenario: Coincidencia normal no se muestra

- **WHEN** un evento tiene `face_count_cliente = 1` y `face_count_servidor = 1` (coinciden)
- **THEN** el bloque de conteo no se muestra: no hay nada que reconciliar

#### Scenario: Discrepancia sin captura no se muestra

- **WHEN** un evento tiene una discrepancia de conteo pero no hay captura asociada
- **THEN** el bloque de conteo no se muestra, porque no hay imagen para inspeccionar la discrepancia

#### Scenario: El dato crudo se conserva

- **WHEN** la UI oculta el bloque de conteo por coincidencia o falta de captura
- **THEN** los valores `face_count_cliente` y `face_count_servidor` permanecen sin cambios en el registro server-side
