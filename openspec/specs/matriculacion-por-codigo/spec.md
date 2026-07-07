# matriculacion-por-codigo Specification

## Purpose
TBD - created by archiving change c-70-matriculacion-por-codigo. Update Purpose after archive.
## Requirements
### Requirement: Cada comisión tiene un código de matriculación único autogenerado y editable
El sistema SHALL asociar a cada comisión un `codigo_matriculacion` **único**. Al crear una comisión, si no se provee un código, el sistema SHALL autogenerar uno derivado del `codigo` de la materia más un sufijo aleatorio corto (p. ej. `PROG1-7K2Q`). El docente SHALL poder proveer o editar el código en el alta/edición de la comisión. La unicidad SHALL verificarse antes de persistir; ante colisión en la generación automática, el sistema SHALL reintentar con otro sufijo hasta obtener un código libre.

#### Scenario: Alta de comisión sin código provisto autogenera uno único
- **WHEN** el docente crea una comisión sin especificar `codigo_matriculacion`
- **THEN** el sistema autogenera un código derivado del código de la materia con un sufijo aleatorio
- **THEN** el código queda persistido en la comisión y es único frente a las comisiones existentes

#### Scenario: Alta de comisión con código provisto por el docente
- **WHEN** el docente crea una comisión especificando un `codigo_matriculacion`
- **THEN** el sistema usa ese código tal cual (previa validación de unicidad) en lugar de autogenerar uno

#### Scenario: Colisión en la generación automática se resuelve reintentando
- **WHEN** el sufijo aleatorio generado coincide con un `codigo_matriculacion` ya existente
- **THEN** el sistema reintenta la generación con otro sufijo hasta obtener un código libre y no falla por la colisión

#### Scenario: Código provisto duplicado es rechazado
- **WHEN** el docente intenta guardar una comisión con un `codigo_matriculacion` que ya pertenece a otra comisión
- **THEN** el sistema rechaza la operación por violación de unicidad y no persiste la comisión

### Requirement: El alumno se auto-matricula a una comisión con un código válido
El sistema SHALL exponer una operación por la cual un alumno autenticado envía un `codigo_matriculacion` y, si el código mapea a una comisión existente, el sistema crea una `inscripcion` que vincula al alumno con esa comisión. La operación SHALL ser **idempotente**: si el alumno ya está inscripto en esa comisión, el sistema NO SHALL crear un registro duplicado y SHALL responder de forma amistosa (no-op / conflicto informado), sin error interno. La operación SHALL respetar la lógica de elegibilidad/`puede_rendir` existente: matricularse NO altera ni saltea las condiciones previas para rendir.

#### Scenario: Matriculación exitosa con código válido
- **WHEN** un alumno autenticado envía un `codigo_matriculacion` que corresponde a una comisión existente y aún no está inscripto en ella
- **THEN** el sistema crea la `inscripcion` que lo vincula con esa comisión
- **THEN** la operación responde éxito con la comisión a la que quedó matriculado

#### Scenario: Matriculación idempotente cuando el alumno ya está inscripto
- **WHEN** un alumno envía un `codigo_matriculacion` de una comisión en la que ya está inscripto
- **THEN** el sistema NO crea un registro duplicado (respeta la unicidad `usuario_id`, `comision_id`)
- **THEN** la operación responde de forma amistosa indicando que ya estaba matriculado (no-op o conflicto informado), sin error interno

#### Scenario: La matriculación respeta la elegibilidad para rendir
- **WHEN** un alumno se matricula por código a una comisión
- **THEN** su capacidad de rendir sigue gobernada por la lógica de elegibilidad/`puede_rendir` existente (consentimiento, referencia biométrica vigente, etc.)
- **THEN** la matriculación por sí sola no habilita a rendir si esas condiciones no se cumplen

### Requirement: Un código de matriculación inválido es rechazado
El sistema SHALL rechazar la auto-matriculación cuando el `codigo_matriculacion` enviado no corresponde a ninguna comisión existente, respondiendo un error claro y sin crear ninguna inscripción.

#### Scenario: Código inexistente rechazado
- **WHEN** un alumno envía un `codigo_matriculacion` que no corresponde a ninguna comisión
- **THEN** el sistema responde un error indicando que el código no es válido
- **THEN** no se crea ninguna inscripción

#### Scenario: Código vacío o malformado rechazado
- **WHEN** un alumno envía un `codigo_matriculacion` vacío o con un formato inaceptable
- **THEN** el sistema rechaza la operación por validación y no crea ninguna inscripción

### Requirement: El docente puede consultar y rotar el código de una comisión
El sistema SHALL permitir al docente consultar el `codigo_matriculacion` vigente de una comisión y rotarlo (regenerar uno nuevo único). Al rotar, el sistema SHALL generar un nuevo código único y reemplazar el anterior; las inscripciones ya existentes SHALL permanecer intactas (rotar el código no desmatricula a nadie).

#### Scenario: Consulta del código vigente
- **WHEN** el docente solicita el `codigo_matriculacion` de una comisión que administra
- **THEN** el sistema retorna el código vigente para que el docente lo comparta

#### Scenario: Rotación del código genera uno nuevo y único
- **WHEN** el docente rota el `codigo_matriculacion` de una comisión
- **THEN** el sistema genera un nuevo código único y reemplaza el anterior
- **THEN** las inscripciones ya existentes en esa comisión permanecen intactas

### Requirement: La auto-matriculación por código coexiste con la inscripción manual
El sistema SHALL mantener el camino de inscripción manual del docente sin cambios y SHALL permitir que ambos caminos —inscripción manual y auto-matriculación por código— operen sobre la misma tabla `inscripcion`. Un alumno matriculado por cualquiera de los dos caminos SHALL quedar inscripto de forma equivalente y SHALL respetar la unicidad `usuario_id`, `comision_id`.

#### Scenario: Inscripción manual sigue funcionando
- **WHEN** el docente inscribe manualmente a un alumno en una comisión
- **THEN** la inscripción se crea por el camino manual existente, sin verse afectada por la nueva funcionalidad de código

#### Scenario: Un alumno inscripto manualmente no se duplica al intentar código
- **WHEN** un alumno que ya fue inscripto manualmente en una comisión envía el `codigo_matriculacion` de esa comisión
- **THEN** el sistema no crea un duplicado y responde de forma idempotente (ya matriculado)

