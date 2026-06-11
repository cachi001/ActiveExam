# identity-match-1to1 Specification

## Purpose
TBD - created by archiving change c-09-biometria-liveness. Update Purpose after archive.
## Requirements
### Requirement: Comparación 1:1 por distancia coseno con umbral conservador
El sistema SHALL comparar el embedding capturado contra el embedding de referencia (cargado en C-07, leído cifrado de la DB) mediante distancia coseno, usando un umbral configurado conservadoramente, de modo que rechazar a un legítimo sea preferido por encima de aceptar a un impostor en este paso (RN-BIO-01, RN-BIO-02, RN-BIO-03, US-004 CA-3).

#### Scenario: Distancia bajo el umbral es match
- **WHEN** la distancia coseno entre el embedding capturado y el de referencia es menor que el umbral configurado
- **THEN** el sistema considera la comparación 1:1 exitosa

#### Scenario: Distancia sobre el umbral no es match
- **WHEN** la distancia coseno es mayor o igual que el umbral configurado
- **THEN** el sistema considera la comparación fallida y no habilita el examen en ese intento

#### Scenario: El embedding de referencia se lee cifrado
- **WHEN** se ejecuta la comparación 1:1
- **THEN** el embedding de referencia se lee cifrado de la DB y no se expone en claro al cliente

