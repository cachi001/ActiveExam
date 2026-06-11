# Spec — exam-configuration

> CRUD de la entidad `Examen` con sus parámetros de monitoreo y la calendarización visible para operaciones. Cada scenario es un caso de test de API.

## ADDED Requirements

### Requirement: CRUD de Examen con parámetros de monitoreo
El sistema SHALL permitir al administrador de exámenes crear, leer, actualizar y dar de baja un `Examen` con nombre, ventana temporal (inicio/fin), umbral de score, política de retención, y el conjunto de detectores activos con sus umbrales (RN-EX-01, US-001 CA-1/CA-2).

#### Scenario: Crear un examen con todos los parámetros
- **WHEN** un administrador de exámenes envía `POST /api/v1/exams` con nombre, ventana temporal, umbral de score, política de retención y detectores activos con umbrales
- **THEN** el sistema crea el examen, lo persiste y devuelve 201 con el identificador del examen y sus parámetros

#### Scenario: Actualizar parámetros de un examen
- **WHEN** un administrador envía `PATCH /api/v1/exams/{id}` modificando el umbral de score o los detectores activos
- **THEN** el sistema persiste los nuevos parámetros y devuelve 200 con el examen actualizado

#### Scenario: Dar de baja un examen sin sesiones iniciadas
- **WHEN** un administrador envía `DELETE /api/v1/exams/{id}` sobre un examen que aún no tiene sesiones iniciadas
- **THEN** el sistema da de baja el examen y devuelve 204

### Requirement: Validación de parámetros del examen
El sistema SHALL validar los parámetros del examen en la capa de aplicación y rechazar configuraciones inválidas con 422 y detalle, antes de persistir: ventana temporal coherente (fin posterior al inicio), umbral de score dentro del rango permitido, detectores restringidos al catálogo conocido y política de retención válida.

#### Scenario: Rechazo de ventana temporal incoherente
- **WHEN** un administrador crea un examen cuya fecha de fin es anterior o igual a la de inicio
- **THEN** el sistema rechaza la creación con 422 indicando que la ventana temporal es inválida, y no persiste nada

#### Scenario: Rechazo de detector desconocido
- **WHEN** un administrador activa un detector que no pertenece al catálogo conocido
- **THEN** el sistema rechaza la operación con 422 indicando el detector inválido

#### Scenario: Rechazo de umbral de score fuera de rango
- **WHEN** un administrador define un umbral de score fuera del rango permitido
- **THEN** el sistema rechaza la operación con 422 indicando el umbral inválido

### Requirement: Calendarización visible para operaciones
El sistema SHALL exponer un listado de exámenes filtrable por ventana temporal y estado, de modo que operaciones pueda planificar con anticipación cuándo el sistema estará bajo SLA estricto (RN-EX-02, US-001 CA-5).

#### Scenario: Listar exámenes por rango de fechas
- **WHEN** se consulta `GET /api/v1/exams?from=&to=` con un rango de fechas
- **THEN** el sistema devuelve los exámenes cuya ventana temporal cae en ese rango, con su estado, para planificación operativa
