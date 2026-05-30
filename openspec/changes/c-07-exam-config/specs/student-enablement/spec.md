# Spec — student-enablement

> Gestión de la lista de estudiantes habilitados por examen. Solo los habilitados pueden iniciar (RN-EX-03).

## ADDED Requirements

### Requirement: Gestión de estudiantes habilitados por examen
El sistema SHALL permitir al administrador de exámenes definir y consultar la lista de estudiantes habilitados para un examen; únicamente los estudiantes de esa lista podrán iniciar la sesión del examen (RN-EX-03, US-001 CA-3).

#### Scenario: Definir la lista de estudiantes habilitados
- **WHEN** un administrador envía `PUT /api/v1/exams/{id}/students` con la lista de estudiantes habilitados
- **THEN** el sistema persiste la lista y devuelve 200 con el conjunto de habilitados del examen

#### Scenario: Consultar la lista de habilitados
- **WHEN** un administrador consulta `GET /api/v1/exams/{id}/students`
- **THEN** el sistema devuelve la lista de estudiantes habilitados para ese examen

#### Scenario: Solo los habilitados pueden iniciar
- **WHEN** un estudiante que NO está en la lista de habilitados intenta iniciar el examen
- **THEN** el sistema rechaza el inicio porque el estudiante no figura entre los habilitados del examen
