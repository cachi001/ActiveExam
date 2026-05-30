# Tasks — C-10 `event-ingestion-transport`

> Implementan el canal de ingesta de eventos y el fan-out a paneles con calidad de producción (TDD). El backend valida la firma de cada evento (zero trust), persiste en TimescaleDB y propaga vía el backplane ganador de C-03. El sistema NUNCA sanciona automáticamente.

## 1. Contrato de evento versionado (capability `event-schema-contract`)

- [x] 1.1 Definir en el dominio el contrato de evento (`id`, `session_id`, `exam_id`, `tipo`, `severidad`, `ts_client`, `ts_backend`, `payload`, `firma`, `schema_version`) con `ts_backend` completado server-side; Done: tipo de dominio + test de campos obligatorios
- [x] 1.2 Definir los tipos y severidades del dominio (RN-EV-04) y el mapeo tipo→severidad; Done: test de mapeo (múltiples rostros → alta, heartbeat → baseline)
- [x] 1.3 Implementar el versionado con compatibilidad hacia atrás: aceptar versiones previas soportadas, rechazar versión no soportada con error explícito; Done: tests de contrato versionado (previa OK, desconocida rechazada)
- [x] 1.4 Test de evento mal formado (falta campo obligatorio) rechazado; Done: test rojo→verde

## 2. Canal WebSocket del estudiante (capability `student-ws-channel`)

- [x] 2.1 Implementar el handler WebSocket bidireccional con handshake (`session_id` + JWT + `last_event_id`); Done: conexión asociada a la sesión
- [x] 2.2 Validar el JWT en el handshake contra el JWKS de Keycloak (firma, exp, aud, iss) y periódicamente durante la sesión (RN-AU-03); Done: test JWT válido acepta / inválido o expirado rechaza
- [x] 2.3 Implementar el transporte bidireccional: eventos/heartbeats cliente→backend y comandos backend→cliente; Done: test de comando entregado por el canal de la sesión
- [x] 2.4 Implementar el heartbeat firmado /5s y su validación como prueba de vida (RN-HB-01); Done: test de heartbeat firmado periódico validado
- [x] 2.5 Test de que la ingesta de evento crítico NO deriva sanción automática (L2.5, RN-RV-07); Done: test verifica persiste+propaga sin sanción

## 3. Validación de firma server-side (capability `event-signature-validation`)

- [x] 3.1 Implementar el verificador de firma HMAC-SHA256 contra la clave de sesión rotativa como puerto de infraestructura; Done: puerto + test de firma válida/ inválida
- [x] 3.2 Conectar la validación ANTES de la persistencia en el caso de uso de ingesta; rechazar y registrar el evento con firma inválida sin persistir ni propagar; Done: test rechazo no persiste ni hace fan-out
- [x] 3.3 Rechazar el evento no firmado (sin campo `firma`); Done: test de evento sin firma rechazado
- [x] 3.4 Validar la firma del heartbeat; heartbeat inválido no cuenta como prueba de vida; Done: test de heartbeat con firma inválida
- [x] 3.5 Producir la versión confiable server-side (re-firma/re-inferencia donde corresponda) como fuente de verdad (RN-GLB-01); Done: test de que lo persistido es la versión verificada server-side

## 4. Persistencia en TimescaleDB (capability `event-persistence-timescale`)

- [x] 4.1 Implementar el repositorio que inserta el evento validado en la hypertable con `ts_backend` completado; Done: test de inserción en hypertable
- [x] 4.2 Garantizar índices `(session_id, ts)` y `(exam_id, ts)` (migración Alembic si C-09 no los dejó); Done: índices presentes
- [x] 4.3 Test de que un evento rechazado NO llega a la hypertable; Done: test verifica cero filas para evento inválido
- [x] 4.4 Implementar la consulta de eventos posteriores a `last_event_id` por `(session_id, ts)` (gancho para C-14); Done: test de query ordenada de faltantes

## 5. Fan-out vía backplane ganador de C-03 (capability `event-fanout-backplane`)

- [x] 5.1 Definir el puerto `EventBackplane` (publish/subscribe) en infraestructura; Done: interfaz + test de doble
- [x] 5.2 Implementar los dos adaptadores intercambiables: Postgres `LISTEN/NOTIFY` y Redis Pub/Sub; seleccionar por configuración el ganador de C-03; Done: ambos adaptadores + selección por config
- [x] 5.3 Conectar el fan-out tras la persistencia: publicar el evento validado a los paneles suscriptos a su sesión/examen; Done: test de propagación a panel suscripto
- [ ] 5.4 Verificar el SLO de propagación evento→panel p99 < 500 ms bajo la carga objetivo; Done: medición p99 < 500 ms (Métrica: p99 < 500 ms)
- [ ] 5.5 Verificar cero pérdida de eventos confirmados ante reconexión de panel / redistribución de instancias (RN-CC-08); Done: test de cero pérdida bajo reconexión

## 6. Integración y contrato downstream

- [x] 6.1 Test de contrato del esquema versionado que C-11…C-15 consumen (snapshot del contrato); Done: contract test verde
- [ ] 6.2 Test e2e del Flujo 3: evento firmado → valida → persiste → fan-out → panel; Done: e2e verde con SLO respetado
- [ ] 6.3 Instrumentar métricas (inserts/s, p99 de fan-out, rechazos de firma, conexiones/instancia) y trazas evento→persist→fan-out→panel (DD-12); Done: métricas y trazas visibles (RN-GLB-05)
