## MODIFIED Requirements

### Requirement: El proctoring del examen persiste eventos en buffer antes de cada envío REST
El sistema SHALL instanciar un `CircularEventBuffer` respaldado por `IndexedDbEventBufferStore` en `useExamProctoring`. Antes de cada llamada a `api.enviarEventoProctoring`, el evento SHALL ser persistido en el buffer con su `id` y payload. Si IndexedDB no está disponible, el sistema SHALL degradar silenciosamente operando sin buffer (comportamiento actual). El payload enviado al backend SHALL incluir el campo `screenshot_sha256_cliente` cuando esté disponible; el schema `IngestEventoIn` SHALL aceptar ese campo (ya no lo rechaza con 422).

#### Scenario: Evento se persiste antes del POST
- **WHEN** ocurre un evento discreto de proctoring durante el examen
- **THEN** el evento se almacena en el buffer IndexedDB antes de que se llame `api.enviarEventoProctoring`
- **THEN** si el POST falla, el evento permanece en el buffer para replay posterior

#### Scenario: IndexedDB no disponible — degradación silenciosa
- **WHEN** `IndexedDbEventBufferStore` lanza excepción al abrirse
- **THEN** el sistema opera sin buffer y continúa el flujo de examen sin interrupciones
- **THEN** no se lanza ningún error visible al alumno

#### Scenario: Payload con screenshot_sha256_cliente aceptado por el backend
- **WHEN** se envía `POST /proctoring/sessions/{id}/events` con el campo `screenshot_sha256_cliente` en el body
- **THEN** el backend responde 201 (no 422)
- **THEN** el evento se persiste en `proctoring_event`

#### Scenario: Error de POST se loguea en consola
- **WHEN** `api.enviarEventoProctoring` falla (422, 500, o error de red)
- **THEN** el sistema loguea el error con `console.error('[proctoring] POST evento falló:', err)`
- **THEN** el examen continúa sin interrupción visible al alumno
- **THEN** el evento permanece en el buffer para drain posterior

## ADDED Requirements

### Requirement: Schema IngestEventoIn acepta screenshot_sha256_cliente
El schema Pydantic `IngestEventoIn` SHALL incluir el campo `screenshot_sha256_cliente: str | None = None`. Este campo representa el SHA-256 del screenshot calculado por el cliente para la primera capa de cadena de custodia (C-49, D5). El campo es opcional y no bloquea la ingestión si está ausente.

#### Scenario: Campo presente en el payload
- **WHEN** el cliente envía `screenshot_sha256_cliente` en el body del POST a `/sessions/{id}/events`
- **THEN** el backend acepta el request sin 422
- **THEN** el campo está disponible para persistencia o comparación con `screenshot_sha256` del servidor

#### Scenario: Campo ausente en el payload
- **WHEN** el cliente no envía `screenshot_sha256_cliente` (campo omitido)
- **THEN** el backend acepta el request sin 422 (el campo es opcional, default None)
- **THEN** el evento se persiste normalmente
