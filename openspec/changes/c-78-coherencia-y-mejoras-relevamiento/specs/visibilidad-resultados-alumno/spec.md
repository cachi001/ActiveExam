# visibilidad-resultados-alumno Specification

## Purpose

Que el alumno no vea ni su nota ni los eventos de proctoring hasta que alguien lo decida
explícitamente, reflejando el flujo real de trabajo docente: primero se revisa, después se
publica.

## Requirements

### Requirement: La nota está oculta por defecto

El sistema SHALL crear todo examen nuevo con `mostrar_nota = nunca`. Al finalizar la
rendición el alumno MUST NOT ver su nota hasta que se publique explícitamente.

#### Scenario: Examen recién creado

- **WHEN** un docente crea un examen sin tocar la configuración de visibilidad
- **THEN** el examen queda en `nunca` y la UI lo marca como la opción recomendada

#### Scenario: El alumno termina de rendir

- **WHEN** un alumno finaliza un examen con `mostrar_nota = nunca`
- **THEN** ve la confirmación de entrega, sin nota

### Requirement: Publicar la nota es una acción explícita y auditada

El sistema SHALL ofrecer una acción "Publicar notas ahora" en el detalle del examen que
haga visible la nota en el momento en que el docente lo decida. La acción MUST quedar
registrada en el audit log con quién la ejecutó y cuándo.

#### Scenario: El docente publica

- **WHEN** un docente con permiso ejecuta "Publicar notas ahora"
- **THEN** los alumnos del examen pasan a ver su nota, y el audit log registra actor y timestamp

#### Scenario: Estado visible sin ambigüedad

- **WHEN** un docente mira el detalle del examen
- **THEN** ve "las notas están ocultas" o "publicadas el {fecha} por {persona}"

### Requirement: La visibilidad de la nota no retrocede

El sistema MUST NOT permitir volver a un estado menos visible una vez que la nota se
mostró. El orden permitido es `nunca` → `al_cerrar` → `inmediata`, siempre hacia adelante.

#### Scenario: Intento de volver a ocultar

- **WHEN** se intenta pasar un examen de `inmediata` a `nunca`
- **THEN** el sistema rechaza el cambio

#### Scenario: Aviso antes de publicar

- **WHEN** el docente va a publicar
- **THEN** la UI le advierte que la acción no se puede deshacer, antes de confirmar

### Requirement: Los eventos de proctoring no se le muestran al alumno por defecto

El sistema SHALL exponer una opción por examen que controle si el alumno ve los eventos
que genera el proctoring mientras rinde, con valor por defecto en **no mostrar**.

#### Scenario: Examen con el default

- **WHEN** un alumno rinde un examen recién creado y el proctoring genera eventos
- **THEN** el panel del alumno no los enumera

#### Scenario: El docente decide mostrarlos

- **WHEN** un docente activa la opción en un examen
- **THEN** los alumnos de ese examen ven los eventos, y los de otros exámenes no
