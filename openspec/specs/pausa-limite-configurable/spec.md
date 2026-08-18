# pausa-limite-configurable Specification

## Purpose
TBD - created by archiving change c-76-panel-supervision-en-vivo. Update Purpose after archive.
## Requirements
### Requirement: Umbral de pausas por sesión en la Configuración del Sistema
La Configuración del Sistema SHALL exponer un umbral `pausas_max_por_sesion` (entero, default 2) editable por quien tiene `configurar_sistema` (`admin_sistema`). El umbral SHALL formar parte de la configuración efectiva consumida por el servicio de pausas al aprobar. El schema de configuración SHALL rechazar campos no declarados (`extra='forbid'`).

#### Scenario: Admin configura el límite de pausas
- **WHEN** un `admin_sistema` establece `pausas_max_por_sesion` en la Configuración del Sistema
- **THEN** el valor queda persistido y disponible en la configuración efectiva

#### Scenario: Default 2 sin configuración explícita
- **WHEN** no se ha configurado `pausas_max_por_sesion`
- **THEN** la configuración efectiva devuelve 2 como valor por defecto

#### Scenario: Solo admin del sistema puede configurarlo
- **WHEN** un usuario sin `configurar_sistema` intenta modificar `pausas_max_por_sesion`
- **THEN** el cambio es rechazado

