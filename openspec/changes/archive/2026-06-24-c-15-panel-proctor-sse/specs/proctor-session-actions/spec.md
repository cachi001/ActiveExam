# Spec — proctor-session-actions

> Acciones del proctor sobre sesiones asignadas: mensajería al estudiante, registro de observaciones y cierre forzado de sesión (US-011 CA-3). Acciones operativas, NO disciplinarias.

## ADDED Requirements

### Requirement: Chat bidireccional proctor↔estudiante
El proctor y el estudiante de una sesión supervisada SHALL poder intercambiar mensajes de texto en ambos sentidos durante el examen. En la implementación slim el canal es REST con polling (no SSE/WS): cada parte publica sus mensajes y consulta los del otro. Los mensajes se persisten vinculados a la sesión.

#### Scenario: Mensaje del proctor entregado al estudiante
- **WHEN** el proctor envía un mensaje a un estudiante de una sesión asignada
- **THEN** el mensaje se persiste con autor `proctor` y queda disponible para que el estudiante lo consulte por su canal (sin pasar por el stream del panel)

#### Scenario: Mensaje del estudiante entregado al proctor
- **WHEN** el estudiante envía un mensaje en una sesión activa
- **THEN** el mensaje se persiste con autor `alumno` y queda disponible para que el proctor lo consulte en el panel

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
