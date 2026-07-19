## ADDED Requirements

> Contexto: el write-back de nota a Moodle (`core_grades_update_grades`) YA existe y
> está especificado en la capability `moodle-grade-writeback` (C-69). Esta capability
> NO lo re-implementa: cubre **operarlo contra el campus real** (config/secreto,
> validación E2E) y las **funciones de lectura** que el proctoring necesita traer DE
> Moodle. El detalle fino de las funciones de lectura se cierra en la sesión de
> exploración en vivo del campus (`campustest.frm.utn.edu.ar`).

### Requirement: Configuración del Moodle real gated por entorno y secreto

La integración con Moodle MUST configurarse por entorno (`MOODLE_BASE_URL`,
`MOODLE_WS_TOKEN`, `courseid`/`cmid` destino) apuntando al campus institucional real.
El token de Web Services MUST tratarse como secreto: inyectado desde el secret manager
(Vault / variable de entorno), NUNCA en el repo, en imágenes, en logs ni en el cliente.
Si `MOODLE_BASE_URL` no está configurado, el sistema MUST degradar de forma segura: la
nota se persiste para sincronización manual y ningún flujo se rompe.

#### Scenario: Sin Moodle configurado el sistema no se rompe
- **WHEN** `MOODLE_BASE_URL` no está seteado
- **THEN** el write-back queda deshabilitado, la nota calculada se persiste en estado sincronizable
- **AND** la finalización del examen y el resto del sistema funcionan normalmente

#### Scenario: El token nunca se expone
- **WHEN** se configura la integración con el token de Web Services del campus real
- **THEN** el token vive solo en el secret manager / entorno del backend
- **AND** no aparece en el repositorio, en las imágenes, en los logs ni en ninguna respuesta al cliente

### Requirement: Validación E2E del write-back contra el campus real

Antes de habilitar el write-back en producción, el sistema MUST validarse de punta a
punta contra el campus real con un usuario de prueba: la nota calculada server-side
llega a la libreta de Moodle del usuario correcto, resuelto por `idnumber` (fallback
email), y el intento queda auditado sin el token. Un fallo de resolución de identidad o
de la Web Service MUST quedar registrado como envío fallido reintenable, sin escribir a
un usuario arbitrario.

#### Scenario: Nota de prueba llega al usuario correcto del campus real
- **WHEN** se finaliza una sesión de examen de prueba con el Moodle real configurado
- **THEN** la nota académica aparece en la libreta del usuario Moodle resuelto por idnumber/email
- **AND** el intento queda en el audit log (alumno, sesión, nota, destino, resultado, timestamp) sin el token

#### Scenario: Identidad no resoluble en el campus real no escribe a nadie
- **WHEN** el alumno de prueba no resuelve a un usuario Moodle único
- **THEN** el envío queda marcado como fallido/pendiente de revisión y no se escribe la nota en ningún usuario

### Requirement: Solo la nota académica humana se sincroniza (L2.5)

Lo que se sincroniza a Moodle MUST ser exclusivamente la nota académica derivada de las
respuestas correctas. El score de proctoring, los flags y las señales de integridad MUST
NOT escribirse en Moodle ni convertirse en una penalización automática de la nota. La
decisión disciplinaria por integridad MUST seguir siendo humana y asíncrona (regla dura
L2.5): el proctoring prioriza para revisión, no emite veredicto ni altera la nota.

#### Scenario: El proctoring no contamina la nota sincronizada
- **WHEN** una sesión con eventos de proctoring registrados sincroniza su nota a Moodle
- **THEN** la nota refleja solo las respuestas correctas, sin ninguna penalización automática derivada del score/flags

### Requirement: Lectura de datos desde Moodle para el proctoring

El sistema MUST poder consultar datos DE Moodle vía sus Web Services para alimentar el
proctoring, sin escribir. El conjunto exacto de funciones se define en la sesión de
exploración en vivo del campus; los candidatos son: padrón/participantes de un curso
(inscripciones reales), disponibilidad/apertura de la actividad de examen, y datos de
identidad del participante. Toda lectura MUST usar el token de Web Services server-side
(nunca el cliente) y MUST tratar la respuesta de Moodle como dato no confiable
(validado en el borde, regla dura #6).

#### Scenario: Lectura server-side con token seguro
- **WHEN** el sistema consulta datos de un curso/usuario a Moodle
- **THEN** la llamada la origina el backend con el token de Web Services; el cliente nunca invoca la WS ni transporta el token

#### Scenario: La respuesta de Moodle se valida en el borde
- **WHEN** el backend recibe datos de una Web Service de Moodle
- **THEN** los valida/normaliza antes de usarlos; ningún dato crudo de Moodle llega a un consumidor que asuma su forma
