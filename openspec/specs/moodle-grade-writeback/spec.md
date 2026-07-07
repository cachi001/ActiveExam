# moodle-grade-writeback Specification

## Purpose
TBD - created by archiving change c-69-examen-plataforma-moodle-lockdown. Update Purpose after archive.
## Requirements
### Requirement: Escribir la nota académica en Moodle vía `core_grades_update_grades`
Al finalizar la sesión de examen, el sistema SHALL calcular la nota académica (a partir de las respuestas correctas, server-side) y SHALL escribirla en Moodle invocando la REST Web Service `core_grades_update_grades` del Moodle configurado. La invocación SHALL incluir el `courseid` y el ítem de calificación / `cmid` destino configurados por el admin, y SHALL autenticarse con el token de Web Services guardado como secreto (nunca en el cliente ni en el repo).

#### Scenario: Finalizar examen escribe la nota en Moodle
- **WHEN** una sesión de examen finaliza y se calcula la nota académica server-side
- **THEN** el sistema invoca `core_grades_update_grades` contra el Moodle configurado con el `courseid`/ítem destino y la nota calculada, autenticando con el token secreto

#### Scenario: El disparo es server-side, no desde el cliente
- **WHEN** se debe devolver la nota a Moodle
- **THEN** el envío lo origina el backend al finalizar la sesión; el cliente del alumno NUNCA invoca la Web Service de Moodle ni transporta el token

### Requirement: Mapeo de identidad alumno ↔ usuario Moodle
El sistema SHALL resolver el usuario Moodle destino a partir de la identidad del alumno usando el `idnumber` de Moodle como criterio por defecto y el email como fallback. Si no se puede resolver un usuario Moodle único para el alumno, el sistema SHALL NOT enviar una nota a un usuario arbitrario y SHALL registrar el envío como fallido para revisión.

#### Scenario: Resolución por idnumber
- **WHEN** el alumno tiene un `idnumber` que corresponde a un usuario Moodle
- **THEN** la nota se asocia a ese usuario Moodle por `idnumber`

#### Scenario: Fallback por email
- **WHEN** el alumno no tiene `idnumber` mapeable pero su email corresponde a un usuario Moodle
- **THEN** la nota se asocia a ese usuario Moodle por email

#### Scenario: Identidad no resoluble no envía a un usuario arbitrario
- **WHEN** no se puede resolver un usuario Moodle único para el alumno
- **THEN** el sistema marca el envío como fallido (pendiente de revisión) y no escribe la nota en ningún usuario

### Requirement: Idempotencia y reintentos del envío
El sistema SHALL persistir el estado del envío de cada nota (p. ej. pendiente / enviado / fallido) y SHALL ser idempotente: reintentar el envío de una misma nota ya confirmada como enviada SHALL NOT producir un envío duplicado a Moodle. Ante un fallo de red o una respuesta de error transitoria de Moodle, el sistema SHALL poder reintentar el envío sin recalcular una nota distinta.

#### Scenario: Reintento no duplica una nota ya enviada
- **WHEN** una nota ya fue confirmada como enviada a Moodle y se dispara un reintento para la misma sesión
- **THEN** el sistema no realiza un segundo envío y conserva el estado "enviado"

#### Scenario: Reintento tras fallo de red
- **WHEN** un envío falla por error de red o error transitorio de Moodle
- **THEN** el sistema deja el envío en estado reintenable y un reintento posterior vuelve a intentar con la misma nota calculada

### Requirement: Manejo de error cuando Moodle no responde
Si Moodle no responde, devuelve un error o el token es inválido, el sistema SHALL NOT perder la nota: SHALL persistir la nota calculada y el estado de fallo, y la finalización del examen del alumno SHALL NOT quedar bloqueada por la indisponibilidad de Moodle. El error SHALL quedar registrado para reintento/revisión.

#### Scenario: Moodle caído no bloquea la finalización del examen
- **WHEN** al finalizar el examen el envío a Moodle falla porque Moodle no responde
- **THEN** la sesión del alumno finaliza normalmente, la nota calculada queda persistida y el envío queda en estado fallido reintenable

#### Scenario: Token inválido se registra como fallo
- **WHEN** Moodle rechaza la invocación por token inválido o sin permisos
- **THEN** el sistema registra el envío como fallido con el motivo y no descarta la nota calculada

### Requirement: Separación entre nota académica y score de proctoring (L2.5)
Lo que el sistema escribe en Moodle SHALL ser exclusivamente la nota académica derivada de las respuestas correctas. El score de proctoring, los flags y las señales de integridad SHALL NOT escribirse en Moodle como calificación ni convertirse en veredicto automático. El proctoring no sanciona ni altera la nota académica de forma automática (regla dura L2.5; decisión humana asíncrona).

#### Scenario: El proctoring no contamina la nota enviada
- **WHEN** se calcula y envía la nota académica de una sesión con eventos de proctoring registrados
- **THEN** la nota enviada a Moodle refleja sólo las respuestas correctas y no incorpora ninguna penalización automática derivada del score/flags de proctoring

### Requirement: Auditoría del envío de nota
Cada intento de envío de nota a Moodle SHALL quedar registrado en el audit log con, al menos: identidad del alumno, examen/sesión, nota enviada, destino (`courseid`/ítem), resultado (éxito/fallo) y marca de tiempo. El token NUNCA SHALL registrarse en el audit log ni en trazas.

#### Scenario: Cada envío deja rastro auditable
- **WHEN** el sistema intenta enviar una nota a Moodle (con éxito o con fallo)
- **THEN** se registra una entrada de auditoría con alumno, sesión, nota, destino, resultado y timestamp, sin exponer el token

### Requirement: REST WS hoy, LTI 1.3/AGS como evolución futura
La devolución de nota SHALL implementarse mediante la REST Web Service `core_grades_update_grades`. La integración por LTI 1.3 + AGS (Assignment and Grade Services) SHALL NOT implementarse en este change y SHALL quedar documentada como evolución futura.

#### Scenario: La vía de retorno de nota es REST WS
- **WHEN** se devuelve la nota del examen a Moodle
- **THEN** se hace por la REST Web Service `core_grades_update_grades`; no existe integración LTI/AGS en este change

