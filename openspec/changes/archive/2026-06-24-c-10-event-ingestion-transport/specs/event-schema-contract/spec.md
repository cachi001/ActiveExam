# Spec — event-schema-contract

> Contrato del evento versionado y firmado: la estructura, los campos obligatorios y la semántica de tipos/severidades del dominio (RN-EV-04, RN-EV-05, `04_modelo_de_datos.md §Evento`). Es el contrato que todos los downstream consumen.

## ADDED Requirements

### Requirement: Esquema de evento versionado y completo
Cada evento SHALL incluir `id`, `session_id`, `exam_id`, `tipo`, `severidad`, `ts_client`, `ts_backend`, `payload` (JSON), `firma` (HMAC-SHA256 con la clave de sesión) y `schema_version`. El `ts_backend` SHALL ser completado por el backend al recibir el evento, no por el cliente.

#### Scenario: Evento con todos los campos obligatorios
- **WHEN** el cliente emite un evento del dominio
- **THEN** el evento contiene `id`, `session_id`, `exam_id`, `tipo`, `severidad`, `ts_client`, `payload`, `firma` y `schema_version`, y el backend completa `ts_backend` al recibirlo

#### Scenario: Evento sin campo obligatorio es inválido
- **WHEN** llega un evento al que le falta un campo obligatorio del esquema (p. ej. `firma` o `schema_version`)
- **THEN** el backend lo rechaza como evento mal formado y no lo persiste

### Requirement: Versionado con compatibilidad hacia atrás
El esquema SHALL ser versionado mediante `schema_version` y SHALL mantener compatibilidad hacia atrás: el backend SHALL aceptar y procesar eventos de versiones de esquema previas soportadas sin rechazarlos por la sola diferencia de versión (RN-EV-05).

#### Scenario: Evento de versión previa soportada se procesa
- **WHEN** llega un evento con un `schema_version` anterior pero soportado
- **THEN** el backend lo interpreta con el contrato de esa versión y lo procesa sin rechazarlo por versión

#### Scenario: Versión no soportada se rechaza explícitamente
- **WHEN** llega un evento con un `schema_version` no reconocido
- **THEN** el backend lo rechaza con un error de contrato explícito (no lo persiste silenciosamente)

### Requirement: Tipos y severidades del dominio definidos
El contrato SHALL definir los tipos de evento del dominio (rostro ausente, múltiples rostros, mirada desviada sostenida, postura, cambio de pestaña/pérdida de foco, monitor adicional, posible cambio de identidad, evidencia corrupta, heartbeat) y su severidad asociada (baseline/media/alta/crítica) según RN-EV-04.

#### Scenario: Tipo de evento del dominio mapea a su severidad
- **WHEN** se ingesta un evento de tipo "múltiples rostros"
- **THEN** el contrato lo clasifica con severidad alta conforme a la tabla de RN-EV-04

#### Scenario: Heartbeat clasificado como baseline, no como anomalía
- **WHEN** se ingesta un heartbeat
- **THEN** el contrato lo trata como señal baseline (prueba de vida) y no como evento de anomalía
