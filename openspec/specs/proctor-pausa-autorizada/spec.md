# proctor-pausa-autorizada Specification

## Purpose
TBD - created by archiving change c-15-panel-proctor-sse. Update Purpose after archive.
## Requirements
### Requirement: Solicitud de pausa por el estudiante
El estudiante SHALL poder solicitar una pausa durante una sesión activa, indicando un motivo. La solicitud se persiste con estado `solicitada` y queda disponible para el proctor.

#### Scenario: Estudiante solicita pausa
- **WHEN** el estudiante solicita una pausa con un motivo en una sesión activa
- **THEN** se crea una pausa con estado `solicitada`, vinculada a la sesión, con el motivo y el timestamp de solicitud

### Requirement: Aprobación o rechazo de la pausa por el proctor
El proctor SHALL poder aprobar o rechazar una pausa solicitada de una sesión que supervisa. Cada resolución se **registra en el audit log** (acción operativa, no veredicto disciplinario).

#### Scenario: Proctor aprueba la pausa
- **WHEN** el proctor aprueba una pausa en estado `solicitada`
- **THEN** la pausa pasa a `aprobada`, se registra el actor y el inicio de la ventana, y se escribe una entrada de audit log de la acción

#### Scenario: Proctor rechaza la pausa
- **WHEN** el proctor rechaza una pausa en estado `solicitada`
- **THEN** la pausa pasa a `rechazada`, se registra el actor y el timestamp, y se escribe una entrada de audit log; la ventana NO se abre

### Requirement: Cierre de la ventana de pausa
El estudiante SHALL poder finalizar (reanudar) una pausa aprobada; la ventana se cierra con su timestamp de fin.

#### Scenario: Estudiante reanuda tras la pausa
- **WHEN** el estudiante reanuda una pausa en estado `aprobada`
- **THEN** la pausa pasa a `finalizada` y se registra el timestamp de fin de la ventana

### Requirement: Contextualización de eventos durante pausa aprobada
Los eventos de proctoring cuyo `ts_backend` cae dentro de una ventana de pausa **aprobada** (`aprobada` o `finalizada`) SHALL **excluirse del cálculo de score**, pero SHALL persistirse, firmarse server-side y permanecer **visibles** para la revisión humana, marcados como "pausa autorizada". El sistema NUNCA borra evidencia ni sanciona/exime automáticamente.

#### Scenario: Eventos en pausa aprobada no suman al score
- **WHEN** se calcula el score de una sesión que tiene eventos con `ts_backend` dentro de una ventana de pausa aprobada
- **THEN** esos eventos NO suman al score, pero siguen persistidos y se devuelven en el detalle marcados como ocurridos durante una pausa autorizada

#### Scenario: La evidencia de la pausa nunca se borra
- **WHEN** una pausa fue aprobada y luego finalizada
- **THEN** todos los eventos de la ventana siguen existiendo en la base, firmados server-side, sin que el sistema emita ningún veredicto automático sobre ellos

