# system-configuration Specification

## Purpose
TBD - created by archiving change c-68-configuracion-sistema-funcional. Update Purpose after archive.
## Requirements
### Requirement: Configuración del Sistema persistida como fuente de verdad
El sistema SHALL persistir la configuración global del proctoring en una tabla tipada `configuracion_sistema` (registro singleton global) que abarque: umbrales de detección (`face_absent_ms`, `multiple_faces_frames`, `gaze_deviation_threshold`, `gaze_sustained_ms`, `gaze_fixation_tolerance`), `umbral_cola_revision`, `detectores_activos`, `retencion_dias_default` y `consent_version_vigente`. Esta tabla SHALL existir tanto en el esquema **full** como en el **slim** (Railway prod). Los valores SHALL ser la fuente de verdad autoritativa server-side (RN-GLB-01, cliente = sensor no confiable).

#### Scenario: La configuración persiste entre reinicios
- **WHEN** un `admin_sistema` edita un umbral y reinicia el backend
- **THEN** el valor editado SHALL leerse desde `configuracion_sistema` (no desde una constante hardcodeada ni desde memoria volátil)

#### Scenario: Tabla presente en slim y full
- **WHEN** se inspecciona el esquema de la base de datos de producción (slim/Railway) y el esquema full
- **THEN** la tabla `configuracion_sistema` SHALL existir en ambos

### Requirement: Edición de configuración restringida a admin_sistema con MFA
El sistema SHALL restringir la edición de la configuración global al rol `admin_sistema` con MFA satisfecho; cualquier otro rol o una sesión sin MFA SHALL recibir 403 (RN-AU-05).

#### Scenario: admin_sistema con MFA edita
- **WHEN** un `admin_sistema` con MFA satisfecho envía una edición de configuración
- **THEN** el sistema autoriza y persiste el cambio

#### Scenario: Rol no autorizado es rechazado
- **WHEN** un usuario con rol distinto de `admin_sistema` intenta editar la configuración global
- **THEN** el sistema responde 403 y no modifica la configuración

#### Scenario: admin_sistema sin MFA es rechazado
- **WHEN** un `admin_sistema` cuya sesión no satisface MFA intenta editar la configuración
- **THEN** el sistema responde 403 exigiendo MFA

### Requirement: Versionado monotónico de la configuración
La configuración global SHALL llevar un número de `version` entero monotónicamente creciente que SHALL incrementarse en cada edición exitosa, de modo que los clientes puedan detectar configuración rancia.

#### Scenario: La versión incrementa al editar
- **WHEN** la configuración se edita exitosamente
- **THEN** el campo `version` SHALL ser estrictamente mayor que el valor anterior

### Requirement: Auditoría inmutable de cada cambio de configuración
Cada edición de configuración SHALL escribir una fila inmutable en `audit_log` con el actor, la acción (`config_update`) y un snapshot del estado anterior y posterior.

#### Scenario: Cambio de config queda auditado
- **WHEN** un `admin_sistema` edita la configuración
- **THEN** una fila `config_update` SHALL persistirse en `audit_log` con actor, before y after, y SHALL ser inmutable

### Requirement: Esquemas estrictos para la configuración
Todos los schemas Pydantic de configuración SHALL declarar `extra='forbid'` y rechazar campos no declarados.

#### Scenario: Campo no declarado es rechazado
- **WHEN** una solicitud de edición incluye un campo no declarado en el schema
- **THEN** el sistema responde 422 y no aplica ningún cambio

