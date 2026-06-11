## 1. Configuración y Setup

- [x] 1.1 Crear `backend/app/config_slim.py` con `SlimSettings(BaseSettings)` que requiera solo `DATABASE_URL`, `FRONTEND_ORIGIN` y `PORT` (default 8000), con `extra='forbid'`
- [x] 1.2 Crear `backend/app/main_slim.py` con `create_slim_app()`: monta `CORSMiddleware` con `FRONTEND_ORIGIN` + `http://localhost:5173`, registra solo el router slim en `/api/v1/proctoring`, expone `app = create_slim_app()`
- [x] 1.3 Verificar que `main_slim.py` NO importa ni carga Keycloak, Vault, MinIO, workers ni telemetría OTLP
- [x] 1.4 Agregar `mediapipe` a `backend/requirements.txt` (Tasks Python API, mismo motor que el cliente, para la re-inferencia server-side). Quitar cualquier referencia a `opencv-python-headless`

## 2. Modelos ORM y Migración Alembic

- [x] 2.1 Crear `backend/app/infrastructure/persistence/models/proctoring.py` con los 3 modelos SQLAlchemy: `ProctoringSessionModel`, `ProctoringEventModel`, `ProctoringBiometriaModel` — snake_case, UUID PK con `gen_random_uuid()`, columnas según el diseño; `screenshot_b64` con comentario `# PRODUCCION: dato sensible Ley 25.326`; `embedding` con comentario `# PRODUCCION: dato sensible; cifrar con KMS; purgar al egreso`
- [x] 2.1b Agregar a `ProctoringEventModel` las columnas `screenshot_sha256` (VARCHAR(64) nullable), `face_count_cliente` (INTEGER nullable), `face_count_servidor` (INTEGER nullable) y `veredicto_reinferencia` (VARCHAR(20) NOT NULL DEFAULT 'no_evaluado'); comentar `screenshot_sha256` con `# PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)`
- [x] 2.2 Crear `backend/migrations/versions/0005_proctoring_slim.py` con `branch_labels = ("slim",)`, `depends_on = None`, `upgrade()` que crea las 3 tablas (incluyendo las columnas `screenshot_sha256`, `face_count_cliente`, `face_count_servidor`, `veredicto_reinferencia` en `proctoring_event`) + índices (`proctoring_event(session_id, ts_backend)`, `proctoring_session(creada_en DESC)`), y `downgrade()` que las elimina en orden inverso
- [x] 2.3 Verificar que `alembic upgrade slim@head` corre en Postgres estándar (sin TimescaleDB) sin error

## 3. Repositorio de Persistencia

- [x] 3.1 Crear `backend/app/infrastructure/persistence/repositories/proctoring.py` con `ProctoringRepository` (async, SQLAlchemy): `crear_sesion()`, `listar_sesiones()`, `obtener_sesion()`, `crear_evento()`, `guardar_biometria()`
- [x] 3.2 `listar_sesiones()` SHALL hacer la query de count de eventos, count de discrepancias (`veredicto_reinferencia = 'discrepancia'`) y calcular score en la capa de repositorio o servicio (no en el router)
- [x] 3.3 `crear_evento()` SHALL persistir además `screenshot_sha256`, `face_count_cliente`, `face_count_servidor` y `veredicto_reinferencia`

## 3bis. Re-inferencia (puerto abstracto + adapter MediaPipe) e Integridad

- [x] 3b.1 Crear `backend/app/application/proctoring/reinferencia.py` con `ReinferenciaPort` (Protocol/ABC, método `evaluar(screenshot_b64, face_count_cliente) -> ResultadoReinferencia`) y el dataclass `ResultadoReinferencia` (`face_count_servidor: int | None`, `veredicto: str`). El puerto queda IGUAL (independiente del motor concreto)
- [x] 3b.2 Proveer el modelo `.task` al backend: copiar/referenciar `frontend/public/mediapipe/face_detector_short_range.task` a `backend/models/` (mismo modelo que el cliente). El adapter resuelve la ruta por env `MEDIAPIPE_MODEL_DIR` (default `backend/models/` en local, `/app/models` en contenedor)
- [x] 3b.3 Crear `backend/app/infrastructure/reinferencia/__init__.py` y `mediapipe_adapter.py` con `MediaPipeReinferencia(ReinferenciaPort)`: decodifica el base64 a imagen, re-detecta rostros con MediaPipe Tasks (`mediapipe.tasks.python.vision.FaceDetector` cargando `face_detector_short_range.task` desde `MEDIAPIPE_MODEL_DIR`), calcula `face_count_servidor` (cantidad de detecciones) y deriva el veredicto (`coincide` | `discrepancia`); ante ImportError de mediapipe, modelo `.task` faltante, sin screenshot o imagen no decodificable → `no_evaluado` (degradación elegante RN-GLB-02), sin levantar excepción. Reusar el detector (singleton) entre invocaciones para evitar recargar el modelo en cada request
- [x] 3b.4 Crear `backend/app/application/proctoring/integridad.py` con `sha256_hex(screenshot_b64) -> str | None` (None si no hay screenshot); comentar `# PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)`

## 4. Capa de Aplicación

- [x] 4.1 Crear `backend/app/application/proctoring/__init__.py` y `session_service.py` con funciones `crear_sesion(db, body)`, `listar_sesiones(db)`, `detalle_sesion(db, session_id)`
- [x] 4.2 Crear `backend/app/application/proctoring/event_service.py` con `ingestar_evento(db, session_id, body, reinferencia: ReinferenciaPort)` — verifica existencia de sesión; calcula `sha256_hex(screenshot)`; invoca `reinferencia.evaluar(screenshot, face_count_cliente)` para obtener `face_count_servidor` + `veredicto`; persiste el evento con todos los campos. Depende del puerto `ReinferenciaPort`, NO importa MediaPipe directamente
- [x] 4.2b Inyectar el adapter `MediaPipeReinferencia` como dependencia del `event_service` (vía FastAPI `Depends` o factory en `main_slim.py`), respetando el desacople puerto/adapter
- [x] 4.3 Crear `backend/app/application/proctoring/biometria_service.py` con `guardar_biometria(db, session_id, body)` — verifica existencia de sesión, persiste biometría
- [x] 4.4 Crear `backend/app/application/proctoring/scoring.py` con `calcular_score(eventos) -> int` usando pesos `{ "bajo": 5, "medio": 20, "alto": 50, "critico": 100 }`

## 5. Schemas Pydantic

- [x] 5.1 Crear `backend/app/presentation/api/v1/proctoring/sessions/schemas.py`: `CrearSesionIn` (modo, exam_id?, etiqueta?), `SesionResumen` (id, modo, etiqueta, creada_en, total_eventos, total_discrepancias, score), `EventoDetalle` (id, tipo, severidad, ts_cliente, ts_backend, payload, screenshot_base64, screenshot_sha256, face_count_cliente, face_count_servidor, veredicto_reinferencia), `SesionDetalle` (+ eventos: list[EventoDetalle] + biometria); todos con `extra='forbid'`
- [x] 5.2 Crear `backend/app/presentation/api/v1/proctoring/events/schemas.py`: `IngestEventoIn` (tipo, severidad enum, ts_cliente, payload?, screenshot_base64?, face_count_cliente?), `IngestEventoOut` (evento_id, veredicto_reinferencia, face_count_servidor, screenshot_sha256); con `extra='forbid'`
- [x] 5.3 Crear `backend/app/presentation/api/v1/proctoring/biometria/schemas.py`: `GuardarBiometriaIn` (liveness_ok, retos_resueltos, embedding?, resultado), `BiometriaOut` (ok: bool); con `extra='forbid'`

## 6. Routers FastAPI

- [x] 6.1 Crear `backend/app/presentation/api/v1/proctoring/sessions/router.py` con: `POST /sessions` → 201, `GET /sessions` → 200, `GET /sessions/{id}` → 200/404
- [x] 6.2 Crear `backend/app/presentation/api/v1/proctoring/events/router.py` con: `POST /sessions/{id}/events` → 201/404; devuelve `evento_id` + `veredicto_reinferencia` + `face_count_servidor` + `screenshot_sha256`; inyecta el `ReinferenciaPort` (adapter MediaPipe) vía `Depends`
- [x] 6.3 Crear `backend/app/presentation/api/v1/proctoring/biometria/router.py` con: `POST /sessions/{id}/biometria` → 200/404
- [x] 6.4 Crear `backend/app/presentation/api/v1/proctoring/router.py` que agregue los 3 sub-routers y el endpoint `GET /health`
- [x] 6.5 Verificar que ningún router slim importa dependencias de auth (JWT, Keycloak, `get_current_user`, etc.)

## 7. Dockerfile.slim

- [x] 7.1 Crear `Dockerfile.slim` en la raíz del repo: base `python:3.12-slim`, instala deps de `backend/requirements.txt` (incluye `mediapipe`), copia código, copia `frontend/public/mediapipe/face_detector_short_range.task` a `/app/models/`, setea `PYTHONPATH=/app` y `MEDIAPIPE_MODEL_DIR=/app/models`, CMD = `alembic upgrade slim@head && uvicorn app.main_slim:app --host 0.0.0.0 --port ${PORT:-8000}`. El build se corre desde la raíz del repo (`docker build -f Dockerfile.slim .`) para acceder a `frontend/public/mediapipe/`
- [x] 7.2 Verificar que el build `docker build -f Dockerfile.slim .` completa sin errores [Verificado 2026-06-11: build OK (exit 0), imagen 1.19GB. 1 warning NO bloqueante: JSONArgsRecommended en CMD (línea 65, shell-form) → DEUDA: pasar CMD a exec/JSON-form para manejo correcto de SIGTERM en Railway.]
- [x] 7.3 Documentar en un comentario del Dockerfile o en un `railway.json` las variables de entorno: `DATABASE_URL`, `FRONTEND_ORIGIN`, `PORT` (auto Railway) y `MEDIAPIPE_MODEL_DIR` (opcional, default `/app/models`)

## 8. Tests de Integración (Postgres real)

- [x] 8.1 Crear `backend/tests/proctoring/test_session_api.py`: tests de `POST /sessions`, `GET /sessions`, `GET /sessions/{id}` contra DB real (testcontainers o Postgres efímero); sin mocks de DB
- [x] 8.2 Crear `backend/tests/proctoring/test_event_ingestion.py`: tests de `POST /sessions/{id}/events` incluyendo evento con screenshot (verifica `screenshot_sha256` poblado), evento con payload, sesión inexistente → 404, severidad inválida → 422; verificar que la respuesta incluye `veredicto_reinferencia`, `face_count_servidor`, `screenshot_sha256`
- [x] 8.3 Crear `backend/tests/proctoring/test_biometria.py`: tests de `POST /sessions/{id}/biometria` incluyendo liveness ok/nok, sesión inexistente → 404
- [x] 8.4 Crear `backend/tests/proctoring/test_scoring.py`: tests unitarios de `calcular_score()` (sin DB); verificar pesos, score cero, score máximo
- [x] 8.5 Crear `backend/tests/proctoring/test_health.py`: test de `GET /api/v1/proctoring/health` con DB disponible → `{ db: "ok" }`
- [x] 8.6 Crear `backend/tests/proctoring/test_reinferencia.py`: tests del adapter `MediaPipeReinferencia` y la degradación elegante — imagen con 1 rostro vs cliente=1 → `coincide`; cliente=2 vs servidor=1 → `discrepancia`; sin screenshot → `no_evaluado`; base64 inválido → `no_evaluado` sin excepción; modelo `.task` faltante / ImportError de mediapipe simulado → `no_evaluado`. Verificar que `event_service` consume el `ReinferenciaPort` (puede inyectarse un fake puerto para casos deterministas, NO se mockea la DB)
- [x] 8.7 Crear `backend/tests/proctoring/test_integridad.py`: tests unitarios de `sha256_hex()` — hash determinista de 64 hex chars para un screenshot dado; `None` cuando no hay screenshot
- [x] 8.8 Ampliar `test_session_api.py` (o nuevo test): verificar que `GET /sessions` devuelve `total_discrepancias` correcto y que `GET /sessions/{id}` incluye `screenshot_sha256`, `veredicto_reinferencia`, `face_count_cliente` y `face_count_servidor` por evento (DB real)

## 9. Verificación de No Regresión

- [x] 9.1 Verificar que los tests existentes de producción siguen pasando (el módulo slim es aditivo y no modifica archivos existentes)
- [x] 9.2 Verificar que `main.py` (producción) no importa `config_slim` ni `main_slim`
- [x] 9.3 Verificar que `alembic upgrade head` (sin branch) no intenta correr `0005_proctoring_slim.py` (branch slim es independiente)
