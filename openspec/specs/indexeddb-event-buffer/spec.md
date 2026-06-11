# indexeddb-event-buffer Specification

## Purpose
TBD - created by archiving change c-14-resiliencia-reconexion. Update Purpose after archive.
## Requirements
### Requirement: Buffer circular local resistente a cortes
El cliente SHALL persistir cada evento en un buffer circular local en IndexedDB; si el WebSocket cae, los eventos SHALL seguir guardándose en el buffer sin pérdida (RN-HB-02).

#### Scenario: Eventos se guardan en el buffer mientras el WS está caído
- **WHEN** el WebSocket está caído y el cliente produce eventos
- **THEN** cada evento se persiste en el buffer IndexedDB local sin perderse

#### Scenario: El buffer sobrevive a la inestabilidad del transporte
- **WHEN** el transporte se interrumpe de forma intermitente
- **THEN** los eventos producidos durante las interrupciones quedan persistidos en el buffer para su posterior reenvío

