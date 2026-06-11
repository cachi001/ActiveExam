# railway-deploy-config Specification

## Purpose
TBD - created by archiving change c-45-backend-proctoring-slim. Update Purpose after archive.
## Requirements
### Requirement: Configuración 12-factor con SlimSettings
El sistema SHALL tener un módulo `app/config_slim.py` con `SlimSettings(BaseSettings)` que lea exclusivamente `DATABASE_URL`, `FRONTEND_ORIGIN` y `PORT` del entorno. Todos los campos de producción (Keycloak, Vault, MinIO, OTEL) NO deben ser requeridos. `SlimSettings` SHALL usar `model_config = ConfigDict(extra='forbid')` para rechazar variables inesperadas. `PORT` SHALL tener default `8000`.

#### Scenario: Arranque con solo DATABASE_URL y FRONTEND_ORIGIN
- **WHEN** el entorno tiene solo `DATABASE_URL` y `FRONTEND_ORIGIN` seteados
- **THEN** `SlimSettings()` carga sin error y `settings.port` vale `8000`

#### Scenario: Variable no declarada rechazada
- **WHEN** el entorno tiene una variable no declarada en `SlimSettings`
- **THEN** la creación de `SlimSettings()` lanza `ValidationError` (extra='forbid')

#### Scenario: DATABASE_URL faltante falla explícito
- **WHEN** `DATABASE_URL` no está en el entorno
- **THEN** `SlimSettings()` falla con `ValidationError` en arranque (twelve-factor: sin default inseguro)

### Requirement: App factory slim independiente del backend de producción
El sistema SHALL tener `app/main_slim.py` con una función `create_slim_app()` que instancie FastAPI, monte `CORSMiddleware` con `FRONTEND_ORIGIN` y `http://localhost:5173`, registre solo los routers slim (`/api/v1/proctoring/*`) y NO intente cargar Keycloak, Vault, MinIO, workers ni observabilidad OTLP. El módulo ASGI SHALL exponerse como `app = create_slim_app()`.

#### Scenario: App arranca sin Keycloak ni Vault en el entorno
- **WHEN** `uvicorn app.main_slim:app` se ejecuta con solo `DATABASE_URL` y `FRONTEND_ORIGIN`
- **THEN** la app arranca sin errores y el healthcheck responde `200`

#### Scenario: Routers de producción no registrados
- **WHEN** la app slim arranca
- **THEN** `GET /api/v1/sessions` (router de producción) devuelve `404` — no está registrado en la app slim

#### Scenario: CORS permite el origen del frontend
- **WHEN** el frontend en `FRONTEND_ORIGIN` hace una solicitud con `Origin: <FRONTEND_ORIGIN>`
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: <FRONTEND_ORIGIN>`

#### Scenario: CORS permite localhost:5173 para desarrollo local
- **WHEN** el frontend local en `http://localhost:5173` hace una solicitud
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: http://localhost:5173`

### Requirement: Migración Alembic en branch slim independiente
El sistema SHALL tener una migración `backend/migrations/versions/0005_proctoring_slim.py` con `branch_labels = ("slim",)` y `depends_on = None`. Esta migración crea las tablas `proctoring_session`, `proctoring_event` y `proctoring_biometria` sin requerir TimescaleDB ni las tablas de producción. El Dockerfile SHALL ejecutar `alembic upgrade slim@head` al boot (NO `alembic upgrade head`).

#### Scenario: Migración crea las 3 tablas slim
- **WHEN** se ejecuta `alembic upgrade slim@head` en una DB vacía (sin tablas de producción)
- **THEN** las tablas `proctoring_session`, `proctoring_event` y `proctoring_biometria` existen en la DB

#### Scenario: Downgrade elimina las tablas slim sin afectar producción
- **WHEN** se ejecuta `alembic downgrade slim@base`
- **THEN** las 3 tablas slim son eliminadas; las tablas de producción (si existen) no son afectadas

#### Scenario: Migración no requiere extensión TimescaleDB
- **WHEN** se ejecuta `alembic upgrade slim@head` en un Postgres estándar sin TimescaleDB
- **THEN** la migración completa sin error

### Requirement: Dockerfile.slim deployable en Railway
El sistema SHALL tener un `Dockerfile.slim` en la raíz del repo que: use `python:3.12-slim` como base, instale dependencias desde `backend/requirements.txt` (incluye `mediapipe`), copie el código del backend, copie el modelo `frontend/public/mediapipe/face_detector_short_range.task` a `/app/models/`, setee `PYTHONPATH=/app` y `MEDIAPIPE_MODEL_DIR=/app/models`, y ejecute como CMD `alembic upgrade slim@head && uvicorn app.main_slim:app --host 0.0.0.0 --port ${PORT:-8000}`. El `PORT` es inyectado automáticamente por Railway. El contexto de build SHALL ser la raíz del repo para que `frontend/public/mediapipe/` sea accesible.

#### Scenario: Build del Dockerfile.slim exitoso
- **WHEN** se ejecuta `docker build -f Dockerfile.slim .` desde la raíz del repo
- **THEN** la imagen se construye sin errores

### Requirement: Modelo MediaPipe provisto al contenedor
El sistema SHALL hacer disponible el modelo `face_detector_short_range.task` (el MISMO que usa el cliente, versionado en `frontend/public/mediapipe/`) dentro del contenedor del backend, en la ruta indicada por `MEDIAPIPE_MODEL_DIR`. El `Dockerfile.slim` SHALL copiar ese `.task` a `/app/models/` en build, de modo que el modelo viaje en la imagen sin descarga en runtime. El adapter de re-inferencia SHALL resolver el modelo por `MEDIAPIPE_MODEL_DIR` (default `/app/models`).

#### Scenario: El modelo .task está presente en la imagen
- **WHEN** se inspecciona el contenedor construido desde `Dockerfile.slim`
- **THEN** existe `/app/models/face_detector_short_range.task` y `MEDIAPIPE_MODEL_DIR` apunta a `/app/models`

#### Scenario: Mismo modelo que el cliente
- **WHEN** se compara el `.task` del backend con `frontend/public/mediapipe/face_detector_short_range.task`
- **THEN** son el mismo archivo (mismo modelo y versión), garantizando consistencia de motor cliente-vs-servidor

#### Scenario: Modelo faltante degrada sin romper
- **WHEN** el `.task` no está en `MEDIAPIPE_MODEL_DIR` en runtime
- **THEN** la re-inferencia devuelve `no_evaluado` (RN-GLB-02) y la ingesta de eventos sigue funcionando

#### Scenario: Boot en Railway ejecuta migración antes de levantar uvicorn
- **WHEN** el contenedor arranca en Railway con `DATABASE_URL` válido
- **THEN** `alembic upgrade slim@head` corre primero (crea tablas si no existen) y luego uvicorn escucha en `$PORT`

#### Scenario: Boot idempotente si las tablas ya existen
- **WHEN** el contenedor se reinicia y las tablas slim ya existen
- **THEN** `alembic upgrade slim@head` detecta que ya está en la versión objetivo y termina sin error; uvicorn arranca normalmente

