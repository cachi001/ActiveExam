# proctor-assignment Specification

## Purpose
TBD - created by archiving change c-07-exam-config. Update Purpose after archive.
## Requirements
### Requirement: Asignación de proctores a un examen
El sistema SHALL permitir al administrador de exámenes asignar uno o más proctores a un examen mediante la entidad `Asignación` proctor↔examen, de modo que el RBAC contextual habilite a esos proctores a observar únicamente los exámenes asignados (RN-AU-07).

#### Scenario: Asignar proctores a un examen
- **WHEN** un administrador envía `PUT /api/v1/exams/{id}/proctors` con uno o más proctores
- **THEN** el sistema crea las asignaciones proctor↔examen y devuelve 200 con la lista de proctores asignados

#### Scenario: La asignación habilita el permiso contextual
- **WHEN** un proctor asignado a un examen consulta sus sesiones
- **THEN** el sistema le permite observar solo las sesiones de los exámenes en los que figura asignado, y no las de exámenes ajenos

