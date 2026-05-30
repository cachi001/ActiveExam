# Tasks — C-19 `retencion-holds`

> Backend FastAPI, Clean/Hexagonal. TimescaleDB + object storage. TDD.

## 1. Motor de retención automática (capability `retention-policy-engine`)

- [ ] 1.1 Definir el modelo de política de retención por tipo de dato (clips, embeddings, eventos, audit log, casos) con plazo configurable; Done: políticas configurables por tipo
- [ ] 1.2 Implementar el job periódico que recorre las políticas y las aplica sin intervención manual (US-014 CA-1); Done: la retención configurada se aplica automáticamente
- [ ] 1.3 Respetar el Object Lock (WORM) de los binarios: no eliminar antes de expirar la retención; Done: clips bajo Object Lock no se borran prematuramente
- [ ] 1.4 Registrar cada aplicación de política en el audit log append-only (qué política, qué dato, cuándo, resultado); Done: cada aplicación deja rastro verificable

## 2. Archivado de chunks de eventos (capability `event-chunk-archival`)

- [ ] 2.1 Respetar la política de compresión de la hypertable (recientes sin comprimir, 7 días–1 año comprimidos); Done: compresión aplicada por antigüedad
- [ ] 2.2 Exportar los chunks > umbral a Parquet en object storage; Done: chunk antiguo exportado a Parquet, verificado
- [ ] 2.3 Eliminar (drop) el chunk de la base activa solo tras verificar la exportación; Done: base activa acotada, histórico en object storage, sin pérdida
- [ ] 2.4 Registrar el archivado en el audit log; Done: archivado trazable

## 3. Holds por caso abierto (capability `retention-holds`)

- [ ] 3.1 Verificar, antes de eliminar/archivar datos sujetos a hold, si existe un caso disciplinario abierto vinculado; Done: detección de hold por caso abierto
- [ ] 3.2 Extender automáticamente la retención de los datos vinculados a un caso abierto (RN-DSR-02); Done: datos bajo hold no se eliminan
- [ ] 3.3 Liberar el hold al cerrarse el caso y devolver los datos al régimen de retención normal; Done: tras cerrar el caso, la retención normal aplica en el siguiente ciclo
- [ ] 3.4 Coordinar con C-17: una erasure diferida por hold se reanuda cuando el hold se libera; Done: gancho de reanudación documentado

## 4. Eliminación del embedding al egreso (capability `embedding-egress-deletion`)

- [ ] 4.1 Detectar el egreso del estudiante y eliminar su embedding biométrico cifrado; Done: embedding eliminado al egreso
- [ ] 4.2 Registrar la eliminación del embedding en el audit log; Done: eliminación trazable sin reexponer el vector

## 5. Tests

- [ ] 5.1 Test: aplicación de política — la retención configurada se aplica automáticamente por tipo de dato; Done: test verde
- [ ] 5.2 Test: hold por caso abierto — los datos vinculados a un caso abierto no se eliminan; al cerrar el caso, vuelven al régimen normal; Done: test verde
- [ ] 5.3 Test: archivado de chunks — un chunk > umbral se exporta a Parquet y se elimina de la base activa solo tras verificar la exportación, sin pérdida; Done: test verde
- [ ] 5.4 Test: eliminación al egreso — el embedding se elimina cuando el estudiante egresa y queda registrado en el audit log; Done: test verde
- [ ] 5.5 Test: trazabilidad — cada operación de retención deja rastro verificable en el audit log sin reexponer PII; Done: test verde
