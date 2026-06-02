## Why

El frontend de proctoring (React/Vite en Vercel) necesita un backend que persista sesiones de detección, eventos con screenshots y resultados biométricos, y los exponga para revisión humana. El backend de producción existente está acoplado a Keycloak, Vault, MinIO WORM, TimescaleDB y workers — una pila imposible de desplegar en Railway para un demo. Se necesita un módulo REST slim, sin auth, deployable en Railway (FastAPI + Postgres administrado), que sea aditivo y no rompa el backend de producción.

## What Changes

- **Nuevo módulo slim** `app/presentation/api/v1/proctoring/` — routers REST sin auth, prefijo `/api/v1/proctoring`.
- **Nueva capa de aplicación** `app/application/proctoring/` — servicios de sesión, eventos e ingesta biométrica.
- **Re-inferencia server-side con MediaPipe (mismo motor que el cliente) detrás de un puerto abstracto** — al ingestar un evento con screenshot, el backend re-detecta rostros sobre la imagen con **MediaPipe Tasks Python** (`FaceDetector`) y produce un **veredicto** (`coincide` | `discrepancia` | `no_evaluado`) comparando `face_count_servidor` vs lo reportado por el cliente. El cliente detecta con MediaPipe; usar el MISMO motor server-side hace la comparación cliente-vs-servidor apples-to-apples (mide manipulación, no diferencias entre motores). La re-inferencia vive detrás del puerto `ReinferenciaPort` con adapter `MediaPipeReinferencia` (patrón DD-17), reemplazable por ONNX sin tocar la app. Materializa RN-GLB-01 (cliente = sensor no confiable) en alcance demo.
- **Integridad liviana SHA-256** — al guardar una screenshot se calcula y persiste su `sha256` (hex) para detectar alteración, sin WORM/Vault.
- **Nuevas tablas Postgres** `proctoring_session`, `proctoring_event`, `proctoring_biometria` — migración Alembic independiente, sin TimescaleDB. `proctoring_event` incluye `screenshot_sha256`, `face_count_cliente`, `face_count_servidor` y `veredicto_reinferencia`.
- **Configuración Railway** — variables de entorno 12-factor (`DATABASE_URL`, `FRONTEND_ORIGIN`, `PORT`), Dockerfile que ejecuta `alembic upgrade head` al boot y levanta uvicorn en `$PORT`.
- **CORS** — permitir `FRONTEND_ORIGIN` (Vercel) + `http://localhost:5173`.
- **Score calculado en backend** — suma de pesos por severidad alineada con `riskWeights` del frontend (sin sancionar, solo priorizar).
- No se modifica ningún router, entidad, migración ni config de producción existente.

## Capabilities

### New Capabilities

- `proctoring-session-api`: CRUD de sesiones de proctoring slim — crear sesión, listar sesiones con score, obtener detalle con eventos y biometría.
- `proctoring-event-ingestion`: Ingestión REST de eventos de detección + screenshots (base64) asociados a una sesión, con re-inferencia server-side (MediaPipe detrás de `ReinferenciaPort`, mismo motor que el cliente), veredicto de coincidencia/discrepancia e integridad SHA-256 del screenshot.
- `proctoring-history`: Endpoint de historial de sesión — detalle completo con todos los eventos (tipo, severidad, ts, payload, screenshot base64, sha256, veredicto de re-inferencia y face_count cliente vs servidor), resultado biométrico y score calculado. Es la pantalla de revisión humana (alimenta el frontend de revisión, C-46).
- `railway-deploy-config`: Configuración de despliegue Railway — Dockerfile, variables de entorno 12-factor, boot con migración automática, CORS parametrizable.

### Modified Capabilities

<!-- No hay capabilities de producción modificadas. El módulo slim es estrictamente aditivo. -->

## Impact

- **Backend** — nuevos archivos en `app/presentation/api/v1/proctoring/`, `app/application/proctoring/`, `app/infrastructure/persistence/models/proctoring.py`, `app/infrastructure/persistence/repositories/proctoring.py`. Nueva migración Alembic `0005_proctoring_slim.py`.
- **Configuración** — nuevo `SlimSettings` (o modo de arranque alternativo) que solo requiere `DATABASE_URL`, `FRONTEND_ORIGIN` y `PORT`. El `Settings` de producción no se toca.
- **Deploy** — `Dockerfile` ajustado (o nuevo `Dockerfile.slim`) con `CMD alembic upgrade head && uvicorn ... --port $PORT`.
- **CORS middleware** montado condicionalmente para el módulo slim.
- **Nueva dependencia**: `mediapipe` (Tasks Python API) para la re-inferencia server-side con el mismo motor que el cliente. NumPy viene como dependencia transitiva. Tradeoff: `mediapipe` es más pesado que OpenCV (imagen Docker más grande, más RAM, cold start más lento en Railway) — aceptado a cambio de consistencia de motor cliente-vs-servidor. No se agrega MinIO, Vault, Keycloak ni RabbitMQ. SQLAlchemy, Alembic y FastAPI ya están presentes.
- **Modelo MediaPipe reusado del cliente**: el servidor carga el MISMO modelo que el cliente — `face_detector_short_range.task` (ya commiteado en `frontend/public/mediapipe/`). En el deploy se copia a `backend/models/` (o se referencia por env `MEDIAPIPE_MODEL_DIR`) para que esté disponible en el contenedor de Railway.
- **Puerto de re-inferencia** `app/application/proctoring/reinferencia.py` (`ReinferenciaPort`) + adapter `app/infrastructure/reinferencia/mediapipe_adapter.py` (`MediaPipeReinferencia`). Degradación elegante (RN-GLB-02): si MediaPipe no carga, el modelo `.task` falta o la imagen no decodifica → veredicto `no_evaluado`, nunca rompe la ingesta.
- **Frontend (Vercel)** — consumirá los endpoints `/api/v1/proctoring/*` por HTTPS.
- **Ley 25.326** — screenshots se tratan como dato sensible; nota de retención/eliminación requerida en el código y la spec.
