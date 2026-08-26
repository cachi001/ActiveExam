# permisos-nm-pertenencia Specification

## Purpose

Definir cómo se resuelve el alcance de lectura y escritura de cada rol a partir de su
pertenencia real (qué comisiones tutorea, qué materias coordina), en vez de por un
alcance global implícito.

## Requirements

### Requirement: Una comisión puede tener varios tutores

El sistema SHALL persistir la relación comisión↔tutor en la tabla `comision_tutor`, con
UNIQUE sobre `(comision_id, tutor_id)`. Una comisión MAY tener cero, uno o varios tutores.

#### Scenario: Se asignan dos tutores a la misma comisión

- **WHEN** un admin asigna el tutor A y luego el tutor B a la comisión C
- **THEN** ambos quedan asignados y los dos ven C como propia

#### Scenario: Asignar dos veces el mismo tutor es idempotente

- **WHEN** se asigna el tutor A a la comisión C dos veces
- **THEN** el sistema no falla y queda una sola fila

### Requirement: Una materia puede tener varios coordinadores

El sistema SHALL persistir la relación materia↔coordinador en `materia_coordinador`, con
UNIQUE sobre `(materia_id, coordinador_id)`.

#### Scenario: Coordinador asignado a dos materias

- **WHEN** el coordinador X está asignado a las materias M1 y M2
- **THEN** ve el contenido de M1 y M2, y solo el de esas

### Requirement: El coordinador falla cerrado sin materias asignadas

El sistema SHALL acotar al COORDINADOR a sus materias asignadas. Un coordinador sin
ninguna materia MUST NOT ver contenido de ninguna: el alcance se gana por asignación
explícita, nunca por omisión.

#### Scenario: Coordinador recién creado

- **WHEN** existe un coordinador sin filas en `materia_coordinador`
- **THEN** los listados de exámenes, sesiones y estadísticas le responden vacío, no completo

#### Scenario: Coordinador pide una materia ajena

- **WHEN** un coordinador consulta explícitamente una materia que no coordina
- **THEN** el sistema responde 403, no el contenido

### Requirement: Solo admin_sistema tiene alcance global

El sistema SHALL reservar el alcance institucional a `admin_sistema`. TUTOR, PROFESOR y
COORDINADOR MUST estar acotados por pertenencia en todo endpoint de lectura de contenido
académico, registro de sesiones y estadísticas.

#### Scenario: Tutor pide el registro de sesiones

- **WHEN** un tutor lista el registro de sesiones
- **THEN** recibe únicamente las de las comisiones donde figura en `comision_tutor`

### Requirement: El tutor no accede a estadísticas institucionales

El sistema MUST NOT otorgar `ver_estadisticas` al rol TUTOR. Los agregados no exponen
datos personales, pero admiten filtrar por cualquier materia, comisión o examen sin
scoping por pertenencia, lo que convertiría el endpoint en una ventana a comisiones ajenas.

#### Scenario: Tutor intenta ver estadísticas

- **WHEN** un usuario con rol TUTOR pide el resumen de estadísticas
- **THEN** el sistema responde 403

### Requirement: Un subject malformado no produce un error de infraestructura

El sistema SHALL validar que el `subject` del token sea un UUID antes de usarlo en una
consulta de pertenencia.

#### Scenario: Token con subject no-UUID

- **WHEN** llega un token cuyo `subject` no es un UUID válido
- **THEN** el sistema responde 403, no un 500 del driver de base de datos
