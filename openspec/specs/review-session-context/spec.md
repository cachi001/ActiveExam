# review-session-context Specification

## Purpose
TBD - created by archiving change c-16-cola-revision-humana. Update Purpose after archive.
## Requirements
### Requirement: Apertura de sesión auditada con propósito declarado
Cada **apertura** de una sesión por un revisor SHALL registrarse en el **audit log con propósito declarado** (RN-RV-03); el audit log es append-only e inmutable.

#### Scenario: Apertura escribe audit log
- **WHEN** el revisor toma/abre una sesión de la cola
- **THEN** se escribe una entrada de audit log con el actor, el timestamp, la sesión y el propósito declarado

### Requirement: Acceso al contexto completo de solo lectura
El revisor SHALL acceder al **contexto completo** de la sesión, de solo lectura: línea de tiempo de eventos, **clips firmados**, **observaciones del proctor**, output de **re-inferencia** server-side y **audit log de accesos previos** (RN-RV-04).

#### Scenario: Contexto completo disponible
- **WHEN** el revisor abre una sesión flaggeada
- **THEN** ve la línea de tiempo de eventos, los clips firmados, las observaciones del proctor, la re-inferencia firmada y el audit log de accesos previos

### Requirement: Clips accesibles vía URL firmada de 15 minutos
La descarga de un clip durante la revisión SHALL realizarse mediante una **URL firmada que expira en 15 minutos** (RN-CC-05), y cada acceso SHALL auditarse con propósito.

#### Scenario: Clip vía URL firmada caduca
- **WHEN** el revisor solicita ver un clip de la sesión
- **THEN** se emite una URL firmada de 15 min, se registra el acceso en el audit log con propósito, y la URL deja de ser válida pasado el plazo

