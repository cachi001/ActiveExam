# event-chunk-archival Specification

## Purpose
TBD - created by archiving change c-19-retencion-holds. Update Purpose after archive.
## Requirements
### Requirement: Compresión de chunks por antigüedad
El sistema SHALL aplicar la política de compresión de la hypertable de eventos: los chunks recientes sin comprimir y los de mayor antigüedad comprimidos.

#### Scenario: Compresión aplicada
- **WHEN** un chunk supera la ventana de "reciente" configurada
- **THEN** el sistema lo comprime conforme a la política

### Requirement: Archivado de chunks a Parquet y eliminación de la base activa
El sistema SHALL exportar los chunks de eventos que superen el umbral de antigüedad a Parquet en object storage y eliminarlos de la base activa solo tras verificar la exportación.

#### Scenario: Chunk antiguo archivado sin pérdida
- **WHEN** un chunk supera el umbral de antigüedad configurado
- **THEN** el sistema lo exporta a Parquet en object storage y, una vez verificada la exportación, lo elimina de la base activa

#### Scenario: No se elimina sin verificar la exportación
- **WHEN** la exportación a Parquet de un chunk no se ha verificado
- **THEN** el sistema NO elimina el chunk de la base activa

### Requirement: Archivado verificable
El sistema SHALL registrar el archivado de chunks en el audit log.

#### Scenario: Archivado registrado
- **WHEN** se archiva un chunk a Parquet
- **THEN** queda una entrada en el audit log que lo documenta

