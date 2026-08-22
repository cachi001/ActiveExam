# armado-examen-aleatorio Specification

## Purpose

Que el examen se arme como en Moodle: definiendo de dónde salen las preguntas y cuántas,
y sorteándolas por alumno al iniciar el intento, en vez de congelar un set único para
todos.

> Referencia: comportamiento de Moodle 5.x, que es la versión del campus
> (`Moodle 5.2.2+`). Desde 4.3 el slot aleatorio guarda la condición de filtro, no las
> preguntas.

## Requirements

### Requirement: El examen guarda la definición del sorteo, no su resultado

El sistema SHALL persistir en el examen la **condición** del sorteo: categoría, si incluye
subcategorías, cantidad y opcionalmente etiqueta. Un examen MAY tener varios tramos (por
ejemplo 5 de una categoría y 5 de otra). El examen MUST NOT congelar el set concreto.

#### Scenario: Se define un tramo aleatorio

- **WHEN** un docente define "10 preguntas al azar de la categoría Listas, incluyendo subcategorías"
- **THEN** el examen guarda esa condición y no una lista de 10 ids

### Requirement: Cada alumno recibe su propio set al iniciar el intento

El sistema SHALL resolver el set concreto de preguntas al iniciar cada intento, y SHALL
persistirlo en el intento para que la corrección y la revisión reconstruyan exactamente lo
que rindió cada alumno.

#### Scenario: Dos alumnos del mismo examen

- **WHEN** dos alumnos inician el mismo examen con un tramo aleatorio
- **THEN** cada uno recibe su propia selección, y cada uno se corrige contra la suya

#### Scenario: Revisión posterior

- **WHEN** un revisor abre el intento de un alumno
- **THEN** ve las preguntas que le tocaron a ese alumno, no las de otro

### Requirement: El sorteo no repite ni pisa las preguntas fijas

El sistema MUST NOT entregar la misma pregunta dos veces dentro de un intento, ni sortear
una que ya esté incluida como pregunta fija del examen.

#### Scenario: Examen con tramos fijos y aleatorios

- **WHEN** un examen tiene 3 preguntas fijas y un tramo de 5 aleatorias de la misma categoría
- **THEN** las 5 sorteadas son distintas entre sí y distintas de las 3 fijas

### Requirement: Un pool insuficiente se avisa, no se completa

El sistema SHALL avisar cuando la categoría tenga menos preguntas disponibles que la
cantidad pedida. MUST NOT completar con repetidas ni entregar menos en silencio.

#### Scenario: Se piden 10 y hay 6

- **WHEN** un tramo pide 10 preguntas de una categoría que tiene 6 disponibles
- **THEN** el sistema lo informa al armar el examen, antes de que un alumno lo rinda

### Requirement: El tope de preguntas se valida contra las disponibles

El sistema SHALL rechazar un tope de preguntas mayor a la cantidad realmente disponible,
validando en el backend y no solo en la UI, con un mensaje que indique el número concreto.

#### Scenario: Tope imposible

- **WHEN** se seleccionan 10 preguntas y se configura un tope de 20
- **THEN** el sistema rechaza el valor indicando que no puede superar las 10 disponibles

### Requirement: La pregunta se puede previsualizar tal como la ve el alumno

El sistema SHALL ofrecer una vista previa de cada pregunta, desde el banco y desde el
armado del examen, que la renderice como la ve el alumno, con su tipo, puntaje, respuesta
correcta y retroalimentación.

#### Scenario: Revisar un import antes de usarlo

- **WHEN** un docente importa preguntas desde Moodle y abre la vista previa de una
- **THEN** la ve renderizada como en la rendición, y puede detectar si el import salió mal

### Requirement: El armado muestra qué se está eligiendo

El sistema SHALL mostrar, al armar el examen, el desglose por categoría: cuántas preguntas
hay disponibles y cuántas se van a sortear.

#### Scenario: Docente arma el examen

- **WHEN** un docente define los tramos del sorteo
- **THEN** ve por categoría el disponible y el pedido, antes de guardar
