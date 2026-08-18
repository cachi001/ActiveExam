# Tasks — c-77 Conexión de MinIO/WORM a la app real (main_activeexam.py)

> Contexto crítico (leer antes de tocar código): `main_activeexam.py` (la app que se despliega en Railway/Render) hoy guarda los screenshots de evidencia (`proctoring_event.screenshot_b64`) **directo en Postgres, cifrados at-rest** (`EvidenceCipher`) — NUNCA usó MinIO/S3. El código de `worm.py`/`presign.py`/`EvidenceCustodyService` (Object Lock Compliance, diseño C-12) existe en el repo pero nunca se conectó a esta app; solo `main.py` (la app "full", vieja, que NO se despliega) lo referencia, y ahí queda en `None` (stub).
>
> Decisión del dueño (2026-08-18, sin datos reales en la DB — todo de prueba): **NO migrar lo existente.** `screenshot_b64` en Postgres se sigue escribiendo exactamente igual que hoy (cero riesgo, cero cambio de comportamiento). MinIO se agrega como **depósito adicional, opcional y tolerante**: si las variables de entorno `MINIO_*` no están configuradas (caso de Render hoy, sin VPS todavía), el sistema se comporta exactamente igual que ahora. Cuando el dueño levante la VPS con MinIO, alcanza con setear las env vars — sin tocar código de nuevo.
>
> Reglas duras aplicables: tests sin mocks de DB (base real/efímera), Pydantic `extra='forbid'`, snake_case Python, PascalCase componentes React, Object Lock SIEMPRE modo Compliance (nunca Governance, D4/RN-CC-06), cliente = sensor no confiable, evidencia sensible cifrada (Ley 25.326).

## 16. SDK real de MinIO detrás del puerto `WormStoragePort`

- [x] 16.1 Agregar `boto3` a las dependencias del backend (`requirements.txt`/`pyproject.toml`, la que use el repo)
- [x] 16.2 Adaptador `Boto3WormStorage` (o `put_fn`/`get_fn` reales inyectados a `ComplianceWormStorage` ya existente en `backend/app/infrastructure/storage/worm.py` — NO reescribir el puerto, ya está bien diseñado) que hable con un cliente S3 de boto3 apuntando a `endpoint_url` configurable (MinIO es S3-compatible), aplicando `ObjectLockMode='COMPLIANCE'` y `ObjectLockRetainUntilDate` en el `put_object`
- [x] 16.3 Tests del adaptador contra un MinIO real en Docker (testcontainers o el servicio de compose de la tarea 18) — sin mocks de boto3/DB (regla dura #4): sube un objeto, lo re-descarga, confirma que el hash coincide; confirma que un intento de sobreescribir/borrar antes de `retain_until` falla (verificación real de Object Lock, no solo que se llamó al SDK)

## 17. Configuración opcional y tolerante (NO rompe Render sin VPS)

- [x] 17.1 Agregar a `backend/app/config_activeexam.py`: `minio_endpoint: str | None`, `minio_access_key: str | None`, `minio_secret_key: str | None`, `minio_bucket_evidencia: str | None`, `minio_use_ssl: bool = True` — TODOS opcionales, default `None`/vacío, NUNCA con valor hardcodeado real
- [x] 17.2 Función `minio_configurado(settings) -> bool` (pura, testeable) que devuelve `True` solo si endpoint+access_key+secret_key+bucket están TODOS presentes — evita arrancar con configuración a medias
- [x] 17.3 Tests: settings sin ninguna var Minio → `minio_configurado` False; con las 4 completas → True; con solo alguna → False (no arranca a medias)

## 18. Wiring en `main_activeexam.py` (tolerante, sin romper el arranque)

- [x] 18.1 En `create_activeexam_app()`: si `minio_configurado(settings)` → construir `app.state.worm_storage` real (Boto3WormStorage de la tarea 16); si no → `app.state.worm_storage = None` (igual que hoy) + UN log claro nivel INFO ("MinIO no configurado: evidencia solo en DB, temporal hasta VPS") — NUNCA levantar excepción por falta de MinIO, el arranque de la app JAMÁS depende de esto (mismo patrón tolerante try/except que ya usa `main.py` para `presign_service`)
- [x] 18.2 En `event_service.py::ingestar_evento`: agregar parámetro opcional `worm_storage: WormStoragePort | None = None`. Si no es `None`, ADEMÁS de persistir `screenshot_b64` en Postgres (sin cambios, comportamiento actual intacto), depositar el mismo binario en el bucket WORM con `object_key` derivado de `session_id`+`evento.id` y `retain_until` (usar la misma política de retención que ya exista en el repo para evidencia — revisar `retention/engine.py` antes de inventar un valor nuevo)
- [x] 18.3 Persistir la referencia del depósito WORM (`object_key`, `uri`, `retain_until`) en columnas nuevas NULLABLE de `proctoring_event` (migración Alembic, branch `activeexam`, down_revision = HEAD real del branch — correr `alembic heads` antes de fijarlo, NO asumir el número) — nulas cuando MinIO no está configurado, para no romper filas existentes
- [x] 18.4 Inyectar `app.state.worm_storage` en el router de eventos (`Depends`, mismo patrón que `reinferencia`/`cipher`) y pasarlo a `ingestar_evento`
- [x] 18.5 Tests (sin mocks de DB, Postgres real + MinIO real en Docker): con `worm_storage=None` el comportamiento es IDÉNTICO al actual (ya cubierto por los tests existentes de `event_service` — correrlos y confirmar que siguen en verde, es la RED de seguridad); con `worm_storage` configurado, el evento se persiste en DB igual que siempre Y ADEMÁS aparece en el bucket con Object Lock; caída de MinIO (endpoint inalcanzable) durante el depósito NO debe tumbar la ingesta del evento — atrapar el error, loguearlo, event se persiste igual (evidencia en DB es la red de seguridad mientras MinIO no esté 100% confiable)

## 19. Dev/local — mirror del stack real

- [x] 19.1 Agregar servicio `minio` a `infra/docker-compose/docker-compose.dev.yml` (imagen oficial `minio/minio`, bucket con Object Lock habilitado desde el arranque — `--console-address` + creación de bucket vía `mc` en un `command`/init container, siguiendo el mismo estilo ya usado en el compose para el seed idempotente)
- [x] 19.2 Setear las env vars `MINIO_*` del backend en `docker-compose.dev.yml` apuntando al servicio `minio` de arriba — en dev, MinIO SIEMPRE está configurado (a diferencia de Render hoy), para que el flujo completo se pueda probar localmente de punta a punta
- [~] 19.3 Actualizar `.env.example` con las 4 variables `MINIO_*` documentadas pero VACÍAS/comentadas — BLOQUEADO: el sandbox de este agente tiene denegado el acceso (Read/Bash/Glob) a cualquier archivo `.env*` en la raíz del repo, incluido `.env.example`. Pendiente: un agente/humano con acceso debe agregar `MINIO_ENDPOINT=`, `MINIO_ACCESS_KEY=`, `MINIO_SECRET_KEY=`, `MINIO_BUCKET_EVIDENCIA=` (vacías, comentadas) siguiendo el mismo estilo que las demás vars opcionales del archivo.

## 20. Cierre

- [x] 20.1 Verificar que el backend arranca sin ninguna variable `MINIO_*` seteada (simular Render de hoy) — cero errores, cero crash, mismo comportamiento que antes de este change
- [x] 20.2 Verificar que el backend arranca CON las 4 variables `MINIO_*` seteadas contra el MinIO local del compose — evidencia nueva aparece en el bucket
- [x] 20.3 `openspec validate c-77-minio-worm-evidencia --strict`
- [x] 20.4 Actualizar `CHANGES.md` con la entrada de c-77
