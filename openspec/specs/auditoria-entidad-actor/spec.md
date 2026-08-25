# auditoria-entidad-actor Specification

## Purpose

Garantizar que cada entrada del audit log pueda resolverse a un actor con nombre y a una
entidad afectada navegable, sin que eso pueda impedir que la acción quede registrada.

## Requirements

### Requirement: La entidad se deriva de la acción cuando el caller no la pasa

El sistema SHALL derivar el tipo de entidad a partir de la acción (`entidad_de_accion`)
cuando el caller registró `entidad_id` sin `entidad`. La escritura del audit log MUST NOT
rechazarse por la ausencia de ese dato: perder el registro de una acción es peor que
registrarla con el tipo derivado.

#### Scenario: Alta de comisión sin entidad explícita

- **WHEN** un caller registra `COMISION_ALTA` con `entidad_id` pero sin `entidad`
- **THEN** la fila queda con entidad `COMISION` y Auditoría puede ofrecer "Ver detalle"

#### Scenario: Acción sin entidad conocida

- **WHEN** la acción no mapea a ninguna entidad
- **THEN** la fila se registra igual, sin entidad, y Auditoría cae al listado del módulo

### Requirement: El actor es una persona identificable, no un UUID crudo

El sistema SHALL registrar como actor el email o username real de quien ejecuta la
acción. MUST NOT persistirse el UUID del subject como identificador visible del actor.

#### Scenario: Pedido DSR

- **WHEN** alguien ejecuta un pedido DSR
- **THEN** el audit log guarda su email o username, no `"{uuid}:dsr"`

### Requirement: Un evento de proctoring linkea a su sesión

El sistema SHALL resolver la sesión dueña de un evento al registrar la verificación de
cadena, para que la navegación lleve al detalle de esa sesión.

#### Scenario: Verificación de cadena sobre un evento

- **WHEN** se audita la verificación de cadena de un evento de proctoring
- **THEN** "Ver detalle" navega al detalle de la sesión que lo contiene, no al listado general
