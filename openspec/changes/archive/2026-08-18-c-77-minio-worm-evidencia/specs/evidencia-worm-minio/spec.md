## ADDED Requirements

### Requirement: Depósito WORM adicional y opcional en MinIO

Al ingestar un evento de proctoring con screenshot, el backend `main_activeexam.py` SHALL depositar el binario ADEMÁS en un bucket MinIO con Object Lock modo Compliance, únicamente cuando las 4 variables `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` y `MINIO_BUCKET_EVIDENCIA` estén TODAS configuradas. El screenshot SHALL seguir persistiéndose en `proctoring_event.screenshot_b64` (Postgres) exactamente igual que antes de este change — el depósito WORM es un mecanismo ADICIONAL, nunca un reemplazo, y Postgres sigue siendo la fuente de verdad.

#### Scenario: MinIO no configurado — comportamiento idéntico al actual
- **WHEN** el backend arranca sin ninguna variable `MINIO_*` seteada (caso Render sin VPS)
- **THEN** el arranque no falla, `app.state.worm_storage` queda en `None`, y la ingesta de eventos persiste el screenshot únicamente en Postgres, sin columnas `worm_*` pobladas

#### Scenario: MinIO configurado — depósito adicional con Object Lock Compliance
- **WHEN** las 4 variables `MINIO_*` están configuradas y se ingesta un evento con screenshot
- **THEN** el evento se persiste en Postgres igual que siempre Y además el binario aparece en el bucket configurado con Object Lock en modo Compliance y `retain_until` igual a la política de retención de evidencia del repo (`RetentionPolicy.default()`)

#### Scenario: Configuración a medias no habilita el depósito
- **WHEN** solo algunas de las 4 variables `MINIO_*` están configuradas (no las 4)
- **THEN** `minio_configurado(settings)` devuelve `False` y el sistema se comporta como si MinIO no estuviera configurado en absoluto

#### Scenario: Caída de MinIO no tumba la ingesta del evento
- **WHEN** MinIO está configurado pero el endpoint es inalcanzable durante el depósito de un evento
- **THEN** el error se atrapa y se loguea, y el evento se persiste igual en Postgres (la evidencia en DB es la red de seguridad mientras MinIO no sea 100% confiable)

### Requirement: Object Lock siempre en modo Compliance

El adaptador `boto3` del puerto `WormStoragePort` SHALL aplicar siempre `ObjectLockMode='COMPLIANCE'` al depositar evidencia — nunca modo Governance — de modo que ningún actor, ni siquiera la cuenta root de MinIO, pueda modificar o borrar la evidencia antes de `retain_until`.

#### Scenario: Un intento de borrado antes de retain_until es rechazado
- **WHEN** se intenta borrar la versión de un objeto de evidencia depositado antes de que venza su `retain_until`
- **THEN** MinIO rechaza la operación (Object Lock Compliance real, verificado contra un servicio MinIO real en los tests — no solo una aserción sobre los argumentos pasados al SDK)

#### Scenario: Un intento de acortar la retención es rechazado
- **WHEN** se intenta fijar una nueva retención más corta que la original sobre un objeto ya depositado
- **THEN** MinIO rechaza la operación
