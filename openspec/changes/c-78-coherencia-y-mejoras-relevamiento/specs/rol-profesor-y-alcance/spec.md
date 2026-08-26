# rol-profesor-y-alcance Specification

## Purpose

Cubrir el hueco entre TUTOR (demasiado poco) y COORDINADOR (demasiado, incluye el
veredicto de integridad), y acotar por pertenencia las pantallas de supervisión.

## ADDED Requirements

### Requirement: Existe el rol PROFESOR

El sistema SHALL ofrecer el rol PROFESOR con las capacidades de gestión académica y
supervisión: crear exámenes, gestionar el banco de preguntas, ver estadísticas, ver el
registro de sesiones y supervisar en vivo.

#### Scenario: Profesor crea un examen

- **WHEN** un usuario con rol PROFESOR crea un examen en una materia a su cargo
- **THEN** el sistema lo permite

### Requirement: El PROFESOR no emite veredicto de integridad

El sistema MUST NOT otorgar al rol PROFESOR la capacidad de emitir el veredicto de
integridad. Esa decisión queda exclusiva del COORDINADOR: quien pone la nota no decide si
hubo fraude.

#### Scenario: Profesor intenta emitir veredicto

- **WHEN** un usuario con rol PROFESOR intenta resolver una sesión con veredicto
- **THEN** el sistema responde 403

#### Scenario: Profesor observa una sesión marcada

- **WHEN** un PROFESOR abre una sesión que superó el umbral de riesgo
- **THEN** ve la evidencia y el score, sin la acción de veredicto

### Requirement: El TUTOR pierde la gestión de exámenes, banco y estadísticas

El sistema MUST NOT permitir al rol TUTOR crear exámenes, gestionar el banco de preguntas
ni ver estadísticas institucionales. La restricción SHALL aplicarse en el backend, no solo
ocultando el ítem del menú.

#### Scenario: Tutor navega directo a la URL

- **WHEN** un TUTOR escribe a mano la ruta del banco de preguntas
- **THEN** el endpoint responde 403, sin importar que el menú no ofreciera el destino

### Requirement: Supervisión en vivo filtra por materia, comisión y examen

El sistema SHALL ofrecer filtros de materia, comisión y examen en la supervisión en vivo
para COORDINADOR y PROFESOR. Para el TUTOR el alcance SHALL estar fijado a sus comisiones,
sin posibilidad de ampliarlo.

#### Scenario: Coordinador filtra

- **WHEN** un COORDINADOR filtra por una comisión de una materia que coordina
- **THEN** ve las sesiones en vivo de esa comisión

#### Scenario: Tutor pide una comisión ajena

- **WHEN** un TUTOR fuerza el filtro hacia una comisión que no tutorea
- **THEN** el backend acota igual el resultado a sus comisiones

### Requirement: El registro de sesiones se acota en la query

El sistema SHALL acotar el registro de sesiones del TUTOR a las comisiones donde figura
como tutor, filtrando en la consulta al backend y NOT en el frontend.

#### Scenario: Tutor lista el registro

- **WHEN** un TUTOR abre el registro de sesiones
- **THEN** la respuesta del backend contiene únicamente sesiones de sus comisiones
