# session-finalization

## MODIFIED Requirements

### Requirement: Score final consolidado idempotente y recomputable
El cálculo del score final SHALL ser **idempotente y reintentable**; si la tarea de cierre falla, el score final SHALL poder recomputarse desde los eventos persistidos, sin pérdida. El cálculo SHALL ponderar los eventos usando los **pesos vivos** leídos desde la configuración persistida (`evento_score_config` + `configuracion_sistema`), NO mapas hardcodeados; el fallback por defecto SHALL usarse solo como red de seguridad de degradación. La consolidación SHALL registrar la `version` de configuración usada, de modo que un cambio posterior de configuración no altere el score de sesiones ya finalizadas.

#### Scenario: Reintento de la consolidación no duplica el score
- **WHEN** la tarea de consolidación se reintenta tras una falla
- **THEN** el score final resultante es el mismo, sin doble conteo, recomputado desde los eventos persistidos

#### Scenario: La consolidación usa los pesos vivos de la config
- **WHEN** se finaliza una sesión tras una edición de pesos en la configuración
- **THEN** el score final SHALL calcularse con los pesos persistidos vigentes (no con `_PESO_SEVERIDAD_DEFAULT`)

#### Scenario: La versión de config queda registrada en la consolidación
- **WHEN** se consolida una sesión
- **THEN** el resultado SHALL registrar la `version` de configuración utilizada en el cálculo
