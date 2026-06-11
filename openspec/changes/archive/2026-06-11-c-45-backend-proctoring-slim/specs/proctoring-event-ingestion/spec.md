## ADDED Requirements

### Requirement: Ingestar evento de detección con screenshot opcional
El sistema SHALL aceptar `POST /api/v1/proctoring/sessions/{id}/events` sin autenticación y persistir un evento de detección en `proctoring_event`. El body SHALL incluir `tipo` (string libre, ej. 'FACE_ABSENT'), `severidad` ('bajo'|'medio'|'alto'|'critico'), `ts_cliente` (datetime ISO 8601), y opcionalmente `payload` (dict), `screenshot_base64` (string base64) y `face_count_cliente` (int). El schema SHALL usar `model_config = ConfigDict(extra='forbid')`. La respuesta SHALL incluir `evento_id` (UUID), `veredicto_reinferencia`, `face_count_servidor` y `screenshot_sha256`. El cliente es un sensor no confiable (RN-GLB-01): el sistema NO confía a ciegas en lo reportado y corrobora server-side mediante re-inferencia (ver requirement de re-inferencia).

#### Scenario: Evento sin screenshot ingresado exitosamente
- **WHEN** el cliente envía `POST /api/v1/proctoring/sessions/{id}/events` con `{ "tipo": "FACE_ABSENT", "severidad": "alto", "ts_cliente": "2026-06-01T10:00:00Z" }`
- **THEN** el sistema crea un registro en `proctoring_event` y devuelve `201` con `{ "evento_id": "<uuid>" }`

#### Scenario: Evento con screenshot base64 ingresado exitosamente
- **WHEN** el cliente envía el body con `screenshot_base64` poblado (string base64 de imagen)
- **THEN** el sistema persiste el screenshot en la columna `screenshot_b64` de `proctoring_event`

#### Scenario: Evento con payload JSON arbitrario
- **WHEN** el cliente incluye `payload: { "confianza": 0.87, "landmarks": 468 }`
- **THEN** el sistema persiste el payload como JSONB sin validación de estructura interna

#### Scenario: Sesión inexistente
- **WHEN** el cliente ingesta un evento para un `session_id` que no existe
- **THEN** el sistema responde `404 Not Found`

#### Scenario: Severidad inválida rechazada
- **WHEN** el cliente envía `severidad: "extremo"` (valor fuera del enum)
- **THEN** el sistema responde `422 Unprocessable Entity`

#### Scenario: Campo extra rechazado
- **WHEN** el cliente envía un campo no declarado en el schema
- **THEN** el sistema responde `422 Unprocessable Entity` (extra='forbid' activo)

### Requirement: Screenshots tratados como datos sensibles
El sistema SHALL documentar en el código que `screenshot_b64` es un dato sensible bajo Ley 25.326. En el demo, los screenshots se persisten en Postgres. Para producción SHALL contemplarse: (a) cifrado at-rest, (b) política de retención máxima (90 días o fin de hold disciplinario), (c) eliminación por ejercicio de DSR. El campo SHALL ser nullable — el cliente puede no enviar screenshot.

#### Scenario: Screenshot nullable no enviado
- **WHEN** el evento no incluye `screenshot_base64`
- **THEN** el sistema persiste `screenshot_b64 = NULL` en la base de datos

#### Scenario: Comentario de retención presente en el código
- **WHEN** se revisa el modelo ORM `proctoring_event`
- **THEN** la columna `screenshot_b64` tiene un comentario `# PRODUCCION: dato sensible Ley 25.326; cifrar at-rest; retención máx. 90 días; purgar por DSR`

### Requirement: Re-inferencia server-side de rostros con MediaPipe detrás de un puerto abstracto
Al ingestar un evento con `screenshot_base64`, el sistema SHALL re-detectar rostros sobre la imagen con **MediaPipe Tasks Python** (`mediapipe.tasks.python.vision.FaceDetector`) — el MISMO motor que usa el cliente — para corroborar lo reportado por el cliente (RN-GLB-01). El sistema SHALL usar el MISMO modelo `.task` que el cliente (`face_detector_short_range.task`), resuelto por la variable de entorno `MEDIAPIPE_MODEL_DIR`. Usar el mismo motor garantiza que el veredicto mida manipulación del cliente y no diferencias entre detectores (apples-to-apples). El sistema SHALL calcular `face_count_servidor` y compararlo con `face_count_cliente` (provisto en el body o derivado del `payload`/`tipo`), produciendo un `veredicto_reinferencia` con valores `coincide` | `discrepancia` | `no_evaluado`. El sistema SHALL persistir `face_count_cliente`, `face_count_servidor` y `veredicto_reinferencia` en el evento. La re-inferencia SHALL vivir detrás de un puerto abstracto `ReinferenciaPort` (interfaz) con un adapter concreto `MediaPipeReinferencia` (patrón DD-17), de modo que el motor pueda sustituirse por ONNX sin modificar la capa de aplicación. La re-inferencia es de alcance demo; producción usa el motor real con re-hashing y firma server-side. El veredicto NUNCA emite juicio disciplinario (L2.5): solo enriquece la evidencia para el revisor humano.

#### Scenario: Veredicto coincide
- **WHEN** el cliente reporta `face_count_cliente=1` y MediaPipe detecta 1 rostro en el screenshot
- **THEN** el evento se persiste con `veredicto_reinferencia = "coincide"` y `face_count_servidor = 1`

#### Scenario: Veredicto discrepancia
- **WHEN** el cliente reporta `MULTIPLE_FACES` (`face_count_cliente=2`) pero MediaPipe detecta 1 rostro
- **THEN** el evento se persiste con `veredicto_reinferencia = "discrepancia"`, `face_count_cliente = 2` y `face_count_servidor = 1`

#### Scenario: Mismo motor y modelo que el cliente
- **WHEN** se revisa el adapter de re-inferencia
- **THEN** usa `mediapipe.tasks.python.vision.FaceDetector` cargando el mismo modelo `.task` que el cliente (`face_detector_short_range.task`) vía `MEDIAPIPE_MODEL_DIR`

#### Scenario: Degradación elegante sin screenshot
- **WHEN** el evento no incluye `screenshot_base64`
- **THEN** el evento se persiste con `veredicto_reinferencia = "no_evaluado"` y `face_count_servidor = NULL`, sin fallar la ingesta

#### Scenario: Degradación elegante ante imagen inválida, MediaPipe no disponible o modelo faltante
- **WHEN** la imagen base64 no decodifica, `mediapipe` no está disponible (ImportError) o el modelo `.task` no existe en `MEDIAPIPE_MODEL_DIR`
- **THEN** el adapter devuelve `veredicto_reinferencia = "no_evaluado"` sin levantar excepción, la ingesta del evento se completa con `201` (RN-GLB-02)

#### Scenario: Puerto abstracto desacopla el motor
- **WHEN** se revisa la capa de aplicación `event_service`
- **THEN** depende de la interfaz `ReinferenciaPort` y no importa directamente MediaPipe (el adapter `MediaPipeReinferencia` vive en `infrastructure/reinferencia/`)

### Requirement: Integridad liviana del screenshot mediante SHA-256
Al persistir un evento con screenshot, el sistema SHALL calcular el `sha256` (hex) del contenido del screenshot y persistirlo en `proctoring_event.screenshot_sha256`. Esto provee integridad básica (detección de alteración) en alcance demo, SIN WORM, Vault, HMAC con clave maestra ni firma encadenada. El código SHALL documentar que producción usa la cadena de custodia criptográfica completa. Si el evento no incluye screenshot, `screenshot_sha256` SHALL ser `NULL`.

#### Scenario: SHA-256 calculado y persistido
- **WHEN** el evento incluye `screenshot_base64`
- **THEN** el sistema persiste `screenshot_sha256` con el hash hex (64 caracteres) del contenido del screenshot y lo devuelve en la respuesta

#### Scenario: SHA-256 nulo sin screenshot
- **WHEN** el evento no incluye `screenshot_base64`
- **THEN** `screenshot_sha256 = NULL`

#### Scenario: Comentario de cadena de custodia presente en el código
- **WHEN** se revisa el cálculo del sha256
- **THEN** existe un comentario `# PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)`
