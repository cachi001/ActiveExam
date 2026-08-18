# proctor-session-actions Specification

## Purpose
TBD - created by archiving change c-15-panel-proctor-sse. Update Purpose after archive.
## Requirements
### Requirement: Chat bidireccional proctor↔estudiante
El tutor (docente de la comisión de la sesión, reemplaza al rol `proctor` eliminado) y el estudiante SHALL poder intercambiar mensajes de texto durante el examen. El **estudiante NO puede iniciar** un hilo de chat: solo SHALL poder enviar mensajes en una sesión donde ya existe al menos un mensaje del tutor. La regla de "quién puede iniciar" SHALL validarse server-side (cliente = sensor no confiable). En la implementación activeexam el canal es REST con polling. Los mensajes se persisten vinculados a la sesión con autor `tutor` o `alumno`.

#### Scenario: Mensaje del tutor entregado al estudiante
- **WHEN** el tutor envía un mensaje a un estudiante de una sesión de su comisión
- **THEN** el mensaje se persiste con autor `tutor` y queda disponible para que el estudiante lo consulte por su canal

#### Scenario: El estudiante responde tras un mensaje del tutor
- **WHEN** el estudiante envía un mensaje en una sesión activa donde ya existe al menos un mensaje del tutor
- **THEN** el mensaje se persiste con autor `alumno` y queda disponible para que el tutor lo consulte en el panel

#### Scenario: El estudiante no puede iniciar el chat
- **WHEN** el estudiante intenta enviar un mensaje en una sesión donde el tutor aún no escribió ningún mensaje
- **THEN** el sistema rechaza el envío (no hay hilo iniciado por el tutor)

### Requirement: Registro de observaciones
El tutor (o coordinador) SHALL poder registrar **observaciones** sobre una sesión que supervisa; las observaciones se persisten como insumo del contexto de revisión (consumido por C-16).

#### Scenario: Observación persistida para revisión
- **WHEN** el tutor registra una observación sobre una sesión de su comisión
- **THEN** la observación se persiste vinculada a la sesión y queda disponible para la revisión humana posterior

### Requirement: Cierre forzado de sesión, operativo y auditado
El tutor SHALL poder **forzar el cierre** de una sesión que supervisa; el cierre forzado cambia el estado de la sesión y se **registra en el audit log**. Es una acción **operativa, NO una sanción disciplinaria** y NO es un veredicto (el veredicto es exclusivo de coordinador/revisor).

#### Scenario: Cierre forzado audita y no sanciona
- **WHEN** el tutor fuerza el cierre de una sesión de su comisión
- **THEN** la sesión cambia de estado, se escribe una entrada de audit log de la acción, y NO se emite ninguna decisión disciplinaria automática (la decisión terminal es humana y del coordinador/revisor, C-16)

#### Scenario: El tutor no dispone de veredicto
- **WHEN** el tutor abre el detalle de una sesión flaggeada
- **THEN** el panel NO le ofrece la acción de veredicto (`revisar_sesion`); solo lectura del dossier y acciones operativas

