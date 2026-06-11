# server-side-reinference Specification

## Purpose
TBD - created by archiving change c-09-biometria-liveness. Update Purpose after archive.
## Requirements
### Requirement: Re-inferencia server-side del clip de verificación
El sistema SHALL re-inferir en el backend, sobre el clip exacto capturado, la verificación de identidad (liveness/embedding/comparación), y SHALL tomar la decisión de habilitación con su propio resultado; el veredicto producido por el cliente SHALL tratarse como señal, no como fuente de verdad (RN-GLB-01).

#### Scenario: El backend re-infiere sobre el clip
- **WHEN** el cliente sube el clip y reporta su resultado de verificación
- **THEN** el backend re-infiere sobre el clip exacto y decide la habilitación con su propio resultado

#### Scenario: Cliente manipulado no determina la decisión
- **WHEN** un cliente reporta "verificado" pero la re-inferencia server-side no confirma la coincidencia
- **THEN** el sistema no habilita el examen, porque la decisión la toma la re-inferencia del backend

