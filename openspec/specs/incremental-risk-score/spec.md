# incremental-risk-score Specification

## Purpose
TBD - created by archiving change c-13-scoring-incremental. Update Purpose after archive.
## Requirements
### Requirement: Score incremental vía continuous aggregate
El score de riesgo por sesión SHALL calcularse **incrementalmente** mediante un **continuous aggregate de TimescaleDB** que se refresca al minuto sobre la hypertable de eventos; las lecturas del score salen del agregado materializado, no de recorrer eventos crudos (CQRS-lite).

#### Scenario: Score actualizado al minuto
- **WHEN** llegan nuevos eventos de una sesión activa
- **THEN** el continuous aggregate refresca el score de esa sesión al minuto, sin recorrer toda la hypertable en cada lectura

### Requirement: Ponderación por severidad, frecuencia y persistencia
El peso de cada evento en el score SHALL combinar su **severidad**, su **frecuencia** y su **persistencia**; un patrón sostenido SHALL pesar más que un pico aislado (RN-SC-02, RN-SC-03).

#### Scenario: Patrón sostenido pesa más que pico aislado
- **WHEN** una sesión presenta un patrón anómalo sostenido en el tiempo y otra un pico aislado equivalente en severidad
- **THEN** el score de la sesión con patrón sostenido es mayor que el de la del pico aislado

#### Scenario: Severidad modula el peso
- **WHEN** se ponderan eventos de severidad crítica frente a eventos de severidad media
- **THEN** los de severidad crítica contribuyen con mayor peso al score

### Requirement: Correlación — eventos correlacionados pesan más que la suma
Cuando eventos de distinto tipo coinciden en una ventana temporal, su contribución combinada al score SHALL ser **mayor que la suma** de sus contribuciones individuales (RN-SC-03).

#### Scenario: Eventos coincidentes superan la suma
- **WHEN** una sesión registra mirada desviada y pérdida de foco simultáneas dentro de la ventana de correlación
- **THEN** la contribución conjunta al score es mayor que la suma de tratar cada evento por separado

