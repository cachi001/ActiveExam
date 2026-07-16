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

### Requirement: La lista de eventos oculta los eventos sin evidencia

La UI del expediente SHALL ocultar de la lista de eventos aquellos que no tienen evidencia asociada (`tiene_evidencia` falso), por ser ruido sin valor para el revisor (p. ej. eventos duplicados navegador/servidor sin captura). El ocultamiento SHALL ser un filtro de **presentación**: el dato crudo y su cadena de custodia SHALL conservarse íntegros server-side (regla dura #6).

#### Scenario: Evento sin evidencia no se lista

- **WHEN** una sesión tiene un evento con `tiene_evidencia` falso
- **THEN** ese evento NO aparece en la lista de eventos del expediente

#### Scenario: Evento con evidencia se lista

- **WHEN** una sesión tiene un evento con evidencia asociada
- **THEN** ese evento aparece en la lista del expediente

#### Scenario: El filtro no altera el dato

- **WHEN** la UI oculta un evento sin evidencia
- **THEN** el registro server-side de ese evento y su cadena de custodia permanecen sin cambios
