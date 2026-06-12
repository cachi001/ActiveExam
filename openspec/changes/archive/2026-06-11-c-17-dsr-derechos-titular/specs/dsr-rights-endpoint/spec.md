# Spec — dsr-rights-endpoint

> Recurso `POST /api/v1/dsr/{type}` del backend. Derechos del titular bajo Ley 25.326 (US-013, FR-13, UC-05; RN-DSR-01).

## ADDED Requirements

### Requirement: Endpoint DSR autenticado por tipo de derecho
El sistema SHALL exponer `POST /api/v1/dsr/{type}` donde `{type}` es uno de `access`, `rectification`, `erasure`, `portability`, autenticando al titular que ejerce el derecho.

#### Scenario: Tipo válido y titular autenticado
- **WHEN** un titular autenticado invoca `POST /api/v1/dsr/access`
- **THEN** el sistema enruta al caso de uso de acceso y responde con los datos personales del titular

#### Scenario: Tipo inválido rechazado
- **WHEN** se invoca `POST /api/v1/dsr/{type}` con un `{type}` no soportado
- **THEN** el sistema rechaza la solicitud con un error de validación

#### Scenario: Sin autenticación
- **WHEN** se invoca el endpoint sin credenciales válidas del titular
- **THEN** el sistema rechaza la solicitud como no autorizada

### Requirement: Derecho de acceso a los datos personales
El sistema SHALL devolver al titular el conjunto de sus datos personales tratados (metadatos de sesiones, eventos, evidencia asociada, embeddings y consentimientos) en formato legible, excluyendo datos de terceros.

#### Scenario: Acceso devuelve los datos del titular
- **WHEN** el titular ejerce el derecho de acceso
- **THEN** la respuesta contiene sus datos personales y NO contiene datos de otros titulares

### Requirement: Derecho de rectificación
El sistema SHALL permitir al titular corregir datos personales rectificables, registrando cada rectificación en el audit log.

#### Scenario: Rectificación registrada
- **WHEN** el titular rectifica un dato personal rectificable
- **THEN** el dato queda corregido y se genera una entrada en el audit log

### Requirement: Derecho de portabilidad
El sistema SHALL exportar los datos personales del titular en un formato estructurado, común y de lectura mecánica.

#### Scenario: Portabilidad exporta formato estructurado
- **WHEN** el titular ejerce el derecho de portabilidad
- **THEN** el sistema entrega un export estructurado y legible por máquina con solo los datos del titular

### Requirement: Respuesta en plazo legal
El sistema SHALL responder a la solicitud DSR dentro del plazo legal configurado; las operaciones que deban diferirse (por hold) SHALL quedar registradas como pendientes con su causa.

#### Scenario: Respuesta dentro del plazo
- **WHEN** se procesa una solicitud DSR
- **THEN** el sistema confirma la operación dentro del plazo legal configurado

#### Scenario: Operación diferida marcada pendiente
- **WHEN** una operación no puede completarse por un hold activo
- **THEN** el sistema la marca como pendiente, registra la causa y no la descarta
