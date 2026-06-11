# proctoring-history Specification

## Purpose
TBD - created by archiving change c-45-backend-proctoring-slim. Update Purpose after archive.
## Requirements
### Requirement: Guardar resultado de verificación biométrica
El sistema SHALL aceptar `POST /api/v1/proctoring/sessions/{id}/biometria` sin autenticación y persistir el resultado de la verificación biométrica del cliente en `proctoring_biometria`. El body SHALL incluir `liveness_ok` (bool), `retos_resueltos` (list[str]), `resultado` (str, ej. 'verificado'|'rechazado'|'pendiente') y opcionalmente `embedding` (string). El schema SHALL usar `model_config = ConfigDict(extra='forbid')`. La respuesta SHALL ser `{ "ok": true }`.

#### Scenario: Biometría guardada exitosamente
- **WHEN** el cliente envía `POST /api/v1/proctoring/sessions/{id}/biometria` con `{ "liveness_ok": true, "retos_resueltos": ["parpadear", "girar_derecha"], "resultado": "verificado" }`
- **THEN** el sistema persiste el registro en `proctoring_biometria` y devuelve `200` con `{ "ok": true }`

#### Scenario: Biometría rechazada (liveness_ok=false)
- **WHEN** el cliente envía `{ "liveness_ok": false, "retos_resueltos": [], "resultado": "rechazado" }`
- **THEN** el sistema persiste igualmente el registro (persiste el resultado sin sanción)

#### Scenario: Embedding opcional como dato sensible
- **WHEN** el cliente incluye `embedding` (representación vectorial del rostro)
- **THEN** el sistema persiste el embedding en `proctoring_biometria.embedding` como TEXT (nullable)
- **THEN** el código documenta `# PRODUCCION: embedding = dato sensible; cifrar con KMS; purgar al egreso del estudiante`

#### Scenario: Sesión inexistente
- **WHEN** el cliente envía biometría para un `session_id` inexistente
- **THEN** el sistema responde `404 Not Found`

#### Scenario: Campo extra rechazado
- **WHEN** el body incluye un campo no declarado en el schema
- **THEN** el sistema responde `422 Unprocessable Entity` (extra='forbid')

### Requirement: Historial completo de sesión para revisión humana
El endpoint `GET /api/v1/proctoring/sessions/{id}` SHALL devolver el historial completo — sesión + score + biometría + todos los eventos (ordenados por `ts_backend ASC`) — que permita a un revisor humano reconstruir lo que pasó durante la sesión y sacar una conclusión propia (L2.5: el sistema nunca sanciona). Cada evento SHALL incluir: `tipo`, `severidad`, `ts_cliente`, `ts_backend`, `payload`, `screenshot_base64`, `screenshot_sha256`, `veredicto_reinferencia` (`coincide`|`discrepancia`|`no_evaluado`), `face_count_cliente` y `face_count_servidor`. El sistema NUNCA emite juicio ni recomendación disciplinaria automática — el revisor humano decide. El score y el veredicto de re-inferencia son solo indicadores de prioridad/contexto. Este endpoint alimenta la pantalla de revisión del frontend (change C-46).

#### Scenario: Historial con eventos ordenados cronológicamente
- **WHEN** el revisor consulta `GET /api/v1/proctoring/sessions/{id}` de una sesión con múltiples eventos
- **THEN** los eventos se devuelven ordenados por `ts_backend ASC`

#### Scenario: Screenshot recuperado en el historial
- **WHEN** un evento tiene `screenshot_b64` no nulo
- **THEN** el campo `screenshot_base64` está presente en la respuesta con el string base64 completo (el frontend puede renderizarlo directamente como `<img src="data:image/..."/>`)

#### Scenario: Veredicto de re-inferencia visible en el historial
- **WHEN** el revisor consulta un evento que tuvo re-inferencia
- **THEN** la respuesta incluye `veredicto_reinferencia`, `face_count_cliente`, `face_count_servidor` y `screenshot_sha256` para que el revisor vea si el servidor corroboró o no lo reportado por el cliente

#### Scenario: Sin veredicto disciplinario en la respuesta
- **WHEN** el revisor consulta el historial
- **THEN** la respuesta NO contiene campos de sanción, penalización ni resultado disciplinario automático — solo hechos registrados (incluido el veredicto de re-inferencia, que es contexto técnico, no juicio) y score de prioridad

### Requirement: Score de priorización alineado con riskWeights del frontend
El backend SHALL calcular el score de riesgo de una sesión como `SUM(peso[severidad] × count_eventos)` con pesos `{ "bajo": 5, "medio": 20, "alto": 50, "critico": 100 }`. Estos valores DEBEN estar alineados con el objeto `riskWeights` del frontend para que la revisión humana vea el mismo número que la UI de proctoring. El score es un indicador de prioridad de revisión, NO un veredicto.

#### Scenario: Score reflejado en listado y detalle
- **WHEN** una sesión tiene eventos de distintas severidades
- **THEN** el mismo valor de `score` aparece tanto en `GET /sessions` como en `GET /sessions/{id}`

#### Scenario: Score cero para sesión sin eventos
- **WHEN** una sesión no tiene eventos
- **THEN** `score = 0`

#### Scenario: Score máximo con eventos críticos
- **WHEN** una sesión tiene 5 eventos 'critico'
- **THEN** `score = 500`

