# liveness-capture-chrome Specification

## Purpose
TBD - created by archiving change c-58-pulido-ux-flujo-examen-login. Update Purpose after archive.
## Requirements
### Requirement: Captura de liveness sin flecha direccional

El overlay de captura biométrica SHALL NOT mostrar una flecha direccional (`←`/`→`) ni el texto "hacia la izquierda"/"hacia la derecha" durante el reto de giro de cabeza. La detección del giro MUST seguir funcionando sin cambios; solo se elimina el indicador visual redundante.

#### Scenario: Reto de giro activo

- **WHEN** el reto activo es `girar_cabeza` y `turnDirection` está definido
- **THEN** el componente de progreso de captura no renderiza ninguna flecha ni texto direccional
- **AND** el progreso del reto (dots/contador) y el resto de la captura siguen visibles y funcionales

#### Scenario: Detección de giro intacta

- **WHEN** el alumno gira la cabeza para resolver el reto
- **THEN** el reto se marca como resuelto igual que antes, sin depender del indicador direccional eliminado

### Requirement: Barra superior de captura sin label contextual

La barra superior del overlay de captura SHALL NOT mostrar el label contextual (`contextLabel`) a la izquierda del botón "Cancelar". El botón "Cancelar" MUST permanecer accesible y alineado, y la prop muerta MUST eliminarse si ningún consumidor la usa.

#### Scenario: Overlay cargado

- **WHEN** el overlay de captura ya cargó (`listoParaMostrar` es true)
- **THEN** la barra superior muestra únicamente el botón "Cancelar" (sin texto contextual a su izquierda)
- **AND** el botón "Cancelar" conserva su comportamiento y posición a la derecha

