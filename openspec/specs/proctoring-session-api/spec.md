# proctoring-session-api Specification

## Purpose
TBD - created by archiving change c-45-backend-proctoring-slim. Update Purpose after archive.
## Requirements
### Requirement: Crear sesión de proctoring
El sistema SHALL aceptar `POST /api/v1/proctoring/sessions` sin autenticación y persistir una nueva sesión en `proctoring_session`. El body SHALL incluir `modo` ('test' o 'examen') y opcionalmente `exam_id` y `etiqueta`. La respuesta SHALL incluir `id` (UUID) y `creada_en` (datetime ISO 8601). El schema de entrada SHALL usar `model_config = ConfigDict(extra='forbid')`.

#### Scenario: Sesión de tipo test creada exitosamente
- **WHEN** el cliente envía `POST /api/v1/proctoring/sessions` con `{"modo": "test"}`
- **THEN** el sistema crea un registro en `proctoring_session` y devuelve `201` con `{ "id": "<uuid>", "creada_en": "<datetime>" }`

#### Scenario: Sesión de tipo examen con exam_id y etiqueta
- **WHEN** el cliente envía `POST /api/v1/proctoring/sessions` con `{"modo": "examen", "exam_id": "EX-001", "etiqueta": "Parcial Cálculo"}`
- **THEN** el sistema persiste todos los campos y devuelve `201` con el `id` de la sesión

#### Scenario: Modo inválido rechazado
- **WHEN** el cliente envía `{"modo": "invalido"}`
- **THEN** el sistema responde `422 Unprocessable Entity` con detalle del error de validación

#### Scenario: Campo extra rechazado
- **WHEN** el cliente envía `{"modo": "test", "campo_desconocido": "x"}`
- **THEN** el sistema responde `422 Unprocessable Entity` (extra='forbid' activo)

### Requirement: Listar sesiones con score y conteo de discrepancias
El sistema SHALL aceptar `GET /api/v1/proctoring/sessions` y devolver la lista de todas las sesiones con `id`, `modo`, `etiqueta`, `creada_en`, `total_eventos` (count), `total_discrepancias` (count de eventos con `veredicto_reinferencia = 'discrepancia'`) y `score` calculado. El score SHALL calcularse como `SUM(peso[severidad] * count_eventos_por_severidad)` con pesos: `critico=100, alto=50, medio=20, bajo=5`. Tanto el score como `total_discrepancias` sirven para priorizar la cola de revisión. El sistema NUNCA emite veredicto disciplinario — solo prioriza la revisión humana.

#### Scenario: Lista con sesiones existentes
- **WHEN** el cliente hace `GET /api/v1/proctoring/sessions` y existen sesiones
- **THEN** el sistema devuelve `200` con un array de objetos `{ id, modo, etiqueta, creada_en, total_eventos, total_discrepancias, score }`

#### Scenario: Lista vacía
- **WHEN** el cliente hace `GET /api/v1/proctoring/sessions` y no hay sesiones
- **THEN** el sistema devuelve `200` con `[]`

#### Scenario: Score calculado correctamente
- **WHEN** una sesión tiene 2 eventos 'critico' y 3 eventos 'medio'
- **THEN** `score = 2*100 + 3*20 = 260`

#### Scenario: Conteo de discrepancias para priorización
- **WHEN** una sesión tiene 3 eventos con `veredicto_reinferencia = 'discrepancia'` y 5 que coinciden
- **THEN** `total_discrepancias = 3`

### Requirement: Obtener detalle de sesión (historial)
El sistema SHALL aceptar `GET /api/v1/proctoring/sessions/{id}` y devolver la sesión completa con todos sus eventos (incluyendo `screenshot_base64`, `screenshot_sha256`, `veredicto_reinferencia`, `face_count_cliente` y `face_count_servidor` si existen) y el resultado biométrico si fue registrado. Este endpoint es la pantalla de revisión humana — el revisor ve todo lo que pasó, incluido si el servidor corroboró lo reportado por el cliente.

#### Scenario: Detalle de sesión existente con eventos y biometría
- **WHEN** el cliente hace `GET /api/v1/proctoring/sessions/{id}` para una sesión con eventos y biometría registrada
- **THEN** el sistema devuelve `200` con `{ id, modo, etiqueta, creada_en, score, eventos: [...], biometria: {...} }`

#### Scenario: Detalle de sesión sin biometría
- **WHEN** la sesión no tiene biometría registrada
- **THEN** el campo `biometria` es `null`

#### Scenario: Sesión no encontrada
- **WHEN** el cliente hace `GET /api/v1/proctoring/sessions/{id}` con un UUID inexistente
- **THEN** el sistema responde `404 Not Found`

### Requirement: Healthcheck del módulo slim
El sistema SHALL exponer `GET /api/v1/proctoring/health` que verifique la conectividad con la base de datos y devuelva `{ "status": "ok", "db": "ok" | "error" }`. Este endpoint NO requiere autenticación y SHALL responder en menos de 2 segundos.

#### Scenario: DB disponible
- **WHEN** la base de datos está accesible
- **THEN** el sistema responde `200` con `{ "status": "ok", "db": "ok" }`

#### Scenario: DB no disponible
- **WHEN** la base de datos no responde
- **THEN** el sistema responde `200` con `{ "status": "ok", "db": "error" }` (el proceso sigue vivo aunque la DB falle)

