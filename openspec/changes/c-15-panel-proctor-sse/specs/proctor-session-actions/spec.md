# Spec — proctor-session-actions

> Acciones del proctor sobre sesiones asignadas: mensajería al estudiante, registro de observaciones y cierre forzado de sesión (US-011 CA-3). Acciones operativas, NO disciplinarias.

## ADDED Requirements

### Requirement: Mensajería al estudiante
El proctor SHALL poder enviar mensajes al estudiante de una sesión que supervisa; la escritura va por el canal de comandos (no por el SSE unidireccional).

#### Scenario: Mensaje entregado al estudiante
- **WHEN** el proctor envía un mensaje a un estudiante de una sesión asignada
- **THEN** el mensaje se entrega al estudiante por el canal del estudiante, sin pasar por el stream SSE del panel

### Requirement: Registro de observaciones
El proctor SHALL poder registrar **observaciones** sobre una sesión; las observaciones se persisten como insumo del contexto de revisión (consumido por C-16).

#### Scenario: Observación persistida para revisión
- **WHEN** el proctor registra una observación sobre una sesión
- **THEN** la observación se persiste vinculada a la sesión y queda disponible para la revisión humana posterior

### Requirement: Cierre forzado de sesión, operativo y auditado
El proctor SHALL poder **forzar el cierre** de una sesión que supervisa; el cierre forzado cambia el estado de la sesión y se **registra en el audit log**. Es una acción **operativa, NO una sanción disciplinaria**.

#### Scenario: Cierre forzado audita y no sanciona
- **WHEN** el proctor fuerza el cierre de una sesión asignada
- **THEN** la sesión cambia de estado, se escribe una entrada de audit log de la acción, y NO se emite ninguna decisión disciplinaria automática (la decisión terminal es humana, C-16)
