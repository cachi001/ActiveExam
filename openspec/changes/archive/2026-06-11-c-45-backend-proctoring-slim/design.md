## Context

El backend de producción (`backend/`) tiene una arquitectura Clean/Hexagonal completa con 9 routers, Keycloak JWT, Vault, MinIO WORM, TimescaleDB, workers y firmas HMAC. Esta pila es inviable en Railway (requiere múltiples servicios, secretos de Vault, extensión TimescaleDB, MinIO, Keycloak). El frontend React en Vercel necesita persistir sesiones + eventos + screenshots y un endpoint de historial para revisar lo que pasó. El alcance es DEMO (L2.5: nunca sancionar, decisión humana siempre).

La solución es un **módulo slim aditivo** dentro del mismo repo — sin tocar el código de producción — que solo necesita `DATABASE_URL` (Postgres administrado de Railway), sea deployable con un solo `docker build + railway up`, y exponga 6 endpoints REST sin auth.

## Goals / Non-Goals

**Goals:**
- Módulo slim estrictamente aditivo (`app/presentation/api/v1/proctoring/`, `app/application/proctoring/`) que no modifica ningún archivo de producción existente.
- 6 endpoints REST bajo `/api/v1/proctoring` — crear sesión, ingestar evento+screenshot, guardar biometría, listar sesiones, detalle de sesión, healthcheck.
- 3 tablas Postgres nuevas (`proctoring_session`, `proctoring_event`, `proctoring_biometria`) con migración Alembic independiente (branch `slim`), sin TimescaleDB.
- Score calculado en backend (suma de pesos por severidad) para priorizar revisión, alineado con `riskWeights` del frontend.
- Deploy Railway 12-factor: solo `DATABASE_URL`, `FRONTEND_ORIGIN`, `PORT`. Boot = `alembic upgrade head` + `uvicorn $PORT`.
- CORS parametrizable: `FRONTEND_ORIGIN` (Vercel) + `localhost:5173`.
- Documentación explícita de retención de screenshots (Ley 25.326).

**Goals (re-inferencia e integridad):**
- Re-inferencia server-side con MediaPipe (mismo motor que el cliente) detrás del puerto abstracto `ReinferenciaPort` (adapter `MediaPipeReinferencia`), que corrobora el conteo de rostros reportado por el cliente y produce un veredicto (`coincide` | `discrepancia` | `no_evaluado`). Materializa RN-GLB-01 en alcance demo.
- Integridad liviana SHA-256 por screenshot (hex persistido), para detectar alteración sin WORM/Vault.

**Non-Goals:**
- Auth (JWT, Keycloak, sesión de usuario).
- Cadena de custodia criptográfica completa (HMAC con clave maestra, WORM, MinIO, Vault, firma server-side). El demo solo hace SHA-256 de integridad básica.
- Re-inferencia de grado producción (re-hashing y firma de evidencia, cadena de custodia, ONNX optimizado, re-inferencia diferida en worker). El demo usa MediaPipe síncrono detrás de un puerto que permite sustituir el motor.
- TimescaleDB / hypertables / continuous aggregates.
- WebSocket, SSE, workers, cola de mensajería.
- Panel de proctor en tiempo real.
- Retención automática de datos, holds, DSR.
- No romper ningún módulo de producción existente.

## Decisions

### D1 — Módulo slim como sub-paquete nuevo, no fork del backend

**Decisión**: Crear `app/presentation/api/v1/proctoring/` y `app/application/proctoring/` como paquetes Python nuevos. El router slim se registra en `main.py` de forma aditiva (sin cambiar rutas existentes).

**Alternativa descartada**: Fork del repo completo o repositorio separado. Descartado porque: (a) la migración Alembic debe correr en la misma DB que el resto si coexisten, (b) mantener dos repos es overhead innecesario, (c) Railway puede deployar un solo repo apuntando al Dockerfile correcto.

**Alternativa descartada**: Reusar los routers de producción (`events`, `sessions`, `evidence`). Descartado porque están acoplados a JWT deps, firmas HMAC, `session_factory` con Vault/MinIO/Keycloak — si faltan esos states la app falla en 500 explícito. El módulo slim necesita ser totalmente independiente de esas dependencies.

### D2 — Configuración: `SlimSettings` separado de `Settings`

**Decisión**: Crear `app/config_slim.py` con `SlimSettings(BaseSettings)` que solo requiere `DATABASE_URL`, `FRONTEND_ORIGIN` y `PORT` (con default `8000`). El `Settings` de producción con `extra='forbid'` rechazaría variables inesperadas del entorno Railway.

**Alternativa descartada**: Agregar los campos slim a `Settings`. Descartado porque `Settings` tiene `extra='forbid'` y muchos campos obligatorios sin default (Keycloak, Vault, MinIO) que no estarán presentes en Railway — la app no arrancaría.

**Decisión de arranque**: Un punto de entrada alternativo `app/main_slim.py` que usa `SlimSettings` y registra solo los routers slim + health. `uvicorn app.main_slim:app` es el CMD del Dockerfile.slim.

### D3 — Migración Alembic en branch `slim` (independiente del branch `default`)

**Decisión**: Crear una migration branch de Alembic llamada `slim` con `branch_labels = ("slim",)` y `depends_on = None` (no depende de la cadena `0001→0002→...`). Esto permite correr `alembic upgrade slim@head` sin necesidad de las extensiones TimescaleDB ni de las tablas de dominio de producción.

**Por qué**: La migración 0001 habilita TimescaleDB y la 0002 crea hypertables — ambas requieren la extensión instalada, que Postgres administrado de Railway no trae por defecto. El módulo slim no necesita TimescaleDB.

**Riesgo**: Si se corre `alembic upgrade head` sin especificar branch, podría intentar correr las migrations de producción. Mitigación: el CMD del Dockerfile.slim usa `alembic upgrade slim@head` explícitamente.

### D4 — Screenshots como TEXT (base64) en `proctoring_event`

**Decisión**: Columna `screenshot_b64 TEXT NULLABLE` en `proctoring_event`. El cliente ya envía base64; almacenarlo como TEXT evita conversiones y simplifica el historial (el cliente puede renderizar directamente con `<img src="data:image/...;base64,..."/>`).

**Alternativa**: `BYTEA` (almacenar bytes decodificados). Más eficiente en espacio pero requiere decodificar en la ingesta y re-encodear al servir. Para el demo el overhead de TEXT es aceptable; para producción se usaría MinIO WORM.

**Ley 25.326**: Screenshots son datos sensibles. El demo los persiste en Postgres. Para producción: (a) cifrado at-rest, (b) política de retención automática (90 días o fin de hold disciplinario), (c) eliminación por DSR. Esto se documenta en la spec y en el código con comentarios `# PRODUCCION: ...`.

### D5 — Score calculado en backend con pesos fijos

**Decisión**: Al listar/detallar sesiones, el backend calcula `score = SUM(peso[severidad] * count)` con pesos: `critico=100, alto=50, medio=20, bajo=5`. Este criterio está alineado con los `riskWeights` del frontend para que la revisión humana vea el mismo score que la UI de proctoring.

**L2.5**: El score solo prioriza la cola de revisión. El backend NUNCA sanciona ni emite veredicto disciplinario.

### D6 — CORS: middleware FastAPI con `FRONTEND_ORIGIN` + `localhost:5173`

**Decisión**: `CORSMiddleware` montado en `main_slim.py` con `allow_origins=[settings.frontend_origin, "http://localhost:5173"]`. Configurable por env sin redeployar.

### D7 — Sin auth en el módulo slim (demo intencional)

**Decisión**: Los 6 endpoints no requieren token ni API key. Es una decisión de alcance del demo; la spec lo documenta explícitamente.

**Riesgo**: Cualquier persona con la URL puede crear sesiones o leer historial. Mitigación para producción: agregar API key de servicio como primer step del hardening.

### D8 — Re-inferencia server-side con MediaPipe (mismo motor que el cliente) detrás de `ReinferenciaPort`

**Decisión**: Al ingestar un evento con `screenshot_base64`, el backend decodifica la imagen y **re-detecta rostros** con **MediaPipe Tasks Python** (`mediapipe.tasks.python.vision.FaceDetector`), usando el MISMO modelo `.task` que el cliente. Calcula `face_count_servidor` (cantidad de detecciones) y lo compara con el conteo que el cliente reporta en el `payload` (campo `face_count`, derivable también del `tipo` del evento). Produce un **veredicto**:

- `coincide` — el conteo del servidor concuerda con el del cliente.
- `discrepancia` — difieren (ej. cliente reporta `MULTIPLE_FACES` / `face_count=2` pero el servidor detecta 1; o el cliente reporta 1 y el servidor detecta 0/2).
- `no_evaluado` — no se pudo evaluar (sin screenshot, MediaPipe no disponible, modelo `.task` ausente, o la imagen no decodifica).

El veredicto, `face_count_cliente` y `face_count_servidor` se persisten en el evento.

**Por qué MediaPipe y NO OpenCV (decisión clave)**: el CLIENTE detecta rostros con MediaPipe (Face Detection / Face Mesh). Si el servidor re-detectara con OpenCV (Haar/DNN), el veredicto `discrepancia` mediría **diferencias entre motores** (Haar vs MediaPipe tienen sensibilidades distintas), no manipulación del cliente. Usando el MISMO motor (MediaPipe) la comparación cliente-vs-servidor es **apples-to-apples**: una discrepancia real apunta a manipulación del stream/screenshot, no a un artefacto del detector. Esto es lo que hace defendible el veredicto ante un revisor humano.

**Reuso del modelo del cliente**: el servidor carga el MISMO archivo que el cliente — `face_detector_short_range.task` (~230 KB, ya commiteado en `frontend/public/mediapipe/`). El adapter lo carga con `FaceDetectorOptions(base_options=BaseOptions(model_asset_path=<ruta>))`. La ruta se resuelve por env `MEDIAPIPE_MODEL_DIR` (default `backend/models/`); el `.task` debe estar disponible en esa ruta dentro del contenedor (ver D8b para el deploy).

**Puerto abstracto (DD-17)**: La re-inferencia vive detrás de la interfaz `ReinferenciaPort` (Protocol / ABC) en `app/application/proctoring/reinferencia.py`:

```python
class ResultadoReinferencia:
    face_count_servidor: int | None
    veredicto: str  # 'coincide' | 'discrepancia' | 'no_evaluado'

class ReinferenciaPort(Protocol):
    def evaluar(self, screenshot_b64: str | None, face_count_cliente: int | None) -> ResultadoReinferencia: ...
```

El adapter concreto `MediaPipeReinferencia` vive en `app/infrastructure/reinferencia/mediapipe_adapter.py`. El `event_service` depende del puerto, no del adapter — para sustituir por ONNX en el futuro solo se cambia el adapter inyectado, sin tocar la capa de aplicación. Esto sigue el patrón DD-17 (motor de visión abstraído detrás de interfaz). El puerto queda IGUAL que con el adapter anterior: solo cambia la implementación concreta.

**Degradación elegante (RN-GLB-02)**: si `mediapipe` no está instalado o falla al cargar (ImportError), si el modelo `.task` no existe en `MEDIAPIPE_MODEL_DIR`, si no hay screenshot, o si la imagen no decodifica → el adapter devuelve `veredicto='no_evaluado'` sin levantar excepción. La ingesta del evento NUNCA falla por la re-inferencia (se persiste el evento igual). El veredicto es informativo para el revisor humano.

**Justificación (RN-GLB-01)**: el cliente es un sensor no confiable; el servidor no le cree al navegador a ciegas. La re-inferencia con MediaPipe es de **alcance demo** (síncrona, sin re-hashing ni firma). En producción se re-infiere con el motor real (MediaPipe/ONNX en worker diferido), se re-hashea y se firma server-side como parte de la cadena de custodia.

**L2.5**: el veredicto `discrepancia` NO sanciona ni emite juicio — solo enriquece la evidencia que ve el revisor humano. La decisión disciplinaria sigue siendo humana.

**Alternativa descartada (OpenCV)**: re-detectar con OpenCV (Haar/DNN). Descartado porque el cliente usa MediaPipe — comparar motores distintos contamina el veredicto con ruido inter-motor en vez de medir manipulación. Tradeoff aceptado: ver "Risks / Trade-offs" sobre el peso de `mediapipe`.

**Alternativa descartada**: re-inferir directamente con MediaPipe dentro del `event_service` sin puerto. Descartado porque viola DD-17 y acopla la aplicación a una librería concreta — cambiar de motor exigiría tocar la lógica de negocio.

### D8b — Provisión del modelo `.task` al contenedor de Railway

**Decisión**: El backend necesita el archivo `face_detector_short_range.task` en runtime. El modelo ya está versionado en el repo bajo `frontend/public/mediapipe/face_detector_short_range.task`. Para que llegue al contenedor:

1. **Copia en build**: el `Dockerfile.slim` copia el `.task` del frontend a `backend/models/` dentro de la imagen (`COPY frontend/public/mediapipe/face_detector_short_range.task /app/models/`). Así el modelo viaja en la imagen y no hay descarga en runtime.
2. **Ruta por env**: el adapter resuelve el modelo con `MEDIAPIPE_MODEL_DIR` (default `/app/models` en el contenedor, `backend/models` en local). Si en el futuro se monta el modelo como volumen o se descarga de un bucket, solo cambia el env — el adapter no.

**Por qué reusar el mismo `.task`**: es lo que garantiza la consistencia de motor de D8. El cliente y el servidor deben usar EXACTAMENTE el mismo modelo y la misma versión; cualquier divergencia reintroduce el problema "discrepancia = diferencia de motor".

**Tradeoff**: el `.task` (~230 KB) se duplica en la imagen del backend. Es trivial en tamaño; la alternativa (ruta compartida entre frontend/backend builds) acoplaría los dos artefactos de deploy. Aceptado.

### D9 — Integridad liviana: SHA-256 por screenshot

**Decisión**: al guardar un evento con screenshot, el backend calcula el `sha256` (hex) sobre el contenido del screenshot (los bytes base64 tal como llegan, criterio determinista y documentado) y lo persiste en `proctoring_event.screenshot_sha256`. Permite detectar alteración posterior del registro de forma básica.

**Non-Goal**: no es la cadena de custodia criptográfica de producción (HMAC con clave maestra en Vault, WORM en MinIO, firma server-side encadenada). El demo solo guarda el hash de integridad. Se documenta en el código con `# PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)`.

**Scope**: el `sha256` se calcula solo si hay screenshot; si no hay screenshot, la columna queda `NULL`.

## Modelo de Datos

```
proctoring_session
  id              UUID PK  DEFAULT gen_random_uuid()
  modo            VARCHAR(20) NOT NULL  -- 'test' | 'examen'
  exam_id         VARCHAR(255) NULLABLE
  etiqueta        VARCHAR(255) NULLABLE
  creada_en       TIMESTAMPTZ NOT NULL  DEFAULT now()
  finalizada_en   TIMESTAMPTZ NULLABLE

proctoring_event
  id              UUID PK  DEFAULT gen_random_uuid()
  session_id      UUID NOT NULL  FK → proctoring_session(id) ON DELETE CASCADE
  tipo            VARCHAR(100) NOT NULL   -- ej. 'FACE_ABSENT', 'MULTIPLE_FACES'
  severidad       VARCHAR(20) NOT NULL    -- 'bajo' | 'medio' | 'alto' | 'critico'
  ts_cliente      TIMESTAMPTZ NOT NULL    -- timestamp reportado por el cliente
  ts_backend      TIMESTAMPTZ NOT NULL  DEFAULT now()
  payload         JSONB NULLABLE
  screenshot_b64  TEXT NULLABLE          -- base64; dato sensible Ley 25.326
  screenshot_sha256   VARCHAR(64) NULLABLE   -- hex SHA-256 del screenshot; integridad liviana (no es cadena de custodia)
  face_count_cliente  INTEGER NULLABLE       -- conteo de rostros reportado por el cliente (derivado de payload/tipo)
  face_count_servidor INTEGER NULLABLE       -- conteo de rostros re-detectado server-side (MediaPipe, mismo motor que el cliente); NULL si no_evaluado
  veredicto_reinferencia VARCHAR(20) NOT NULL DEFAULT 'no_evaluado'  -- 'coincide' | 'discrepancia' | 'no_evaluado'

proctoring_biometria
  id              UUID PK  DEFAULT gen_random_uuid()
  session_id      UUID NOT NULL  FK → proctoring_session(id) ON DELETE CASCADE
  liveness_ok     BOOLEAN NOT NULL
  retos_resueltos JSONB NOT NULL  DEFAULT '[]'
  embedding       TEXT NULLABLE   -- dato sensible; solo en demo; prod: cifrar+purgar
  resultado       VARCHAR(50) NOT NULL   -- ej. 'verificado', 'rechazado', 'pendiente'
  registrada_en   TIMESTAMPTZ NOT NULL  DEFAULT now()
```

Índices: `proctoring_event(session_id, ts_backend)`, `proctoring_session(creada_en DESC)`.

## Estructura de Archivos

```
backend/
  app/
    config_slim.py                          # SlimSettings (DATABASE_URL, FRONTEND_ORIGIN, PORT)
    main_slim.py                            # App factory slim (sin Keycloak/Vault/MinIO)
    presentation/api/v1/proctoring/
      __init__.py
      router.py                             # Registra sub-routers session + event + bio + health
      sessions/
        router.py                           # POST /sessions, GET /sessions, GET /sessions/{id}
        schemas.py                          # Pydantic in/out con extra='forbid'
      events/
        router.py                           # POST /sessions/{id}/events
        schemas.py
      biometria/
        router.py                           # POST /sessions/{id}/biometria
        schemas.py
    application/proctoring/
      __init__.py
      session_service.py                    # crear_sesion, listar_sesiones, detalle_sesion
      event_service.py                      # ingestar_evento (invoca ReinferenciaPort + sha256)
      biometria_service.py                  # guardar_biometria
      scoring.py                            # calcular_score(eventos) → int
      reinferencia.py                       # ReinferenciaPort (Protocol) + ResultadoReinferencia
      integridad.py                         # sha256_hex(screenshot_b64) → str | None
    infrastructure/persistence/
      models/proctoring.py                  # SQLAlchemy ORM models (3 tablas)
      repositories/proctoring.py            # ProctoringRepository (CRUD)
    infrastructure/reinferencia/
      __init__.py
      mediapipe_adapter.py                  # MediaPipeReinferencia (implementa ReinferenciaPort, FaceDetector Tasks API, mismo modelo que el cliente)
  models/
    face_detector_short_range.task          # MISMO modelo que frontend/public/mediapipe/ (copiado en build); ruta por MEDIAPIPE_MODEL_DIR
  migrations/versions/
    0005_proctoring_slim.py                 # branch 'slim', depends_on=None
Dockerfile.slim                             # COPY .task del frontend + CMD: alembic upgrade slim@head + uvicorn main_slim
```

## Endpoints

```
POST   /api/v1/proctoring/sessions
  Body:  { modo: 'test'|'examen', exam_id?: str, etiqueta?: str }
  → 201  { id: uuid, creada_en: datetime }

POST   /api/v1/proctoring/sessions/{id}/events
  Body:  { tipo: str, severidad: 'bajo'|'medio'|'alto'|'critico',
            ts_cliente: datetime, payload?: dict, screenshot_base64?: str,
            face_count_cliente?: int }
  → 201  { evento_id: uuid, veredicto_reinferencia: 'coincide'|'discrepancia'|'no_evaluado',
            face_count_servidor: int | null, screenshot_sha256: str | null }
  Nota: el backend re-detecta rostros (MediaPipe, mismo motor/modelo que el cliente) sobre el screenshot y calcula sha256.
        La re-inferencia degrada a 'no_evaluado' sin romper la ingesta (RN-GLB-02).

POST   /api/v1/proctoring/sessions/{id}/biometria
  Body:  { liveness_ok: bool, retos_resueltos: list[str],
            embedding?: str, resultado: str }
  → 200  { ok: true }

GET    /api/v1/proctoring/sessions
  → 200  [ { id, modo, etiqueta, creada_en, total_eventos: int,
             total_discrepancias: int, score: int } ]

GET    /api/v1/proctoring/sessions/{id}
  → 200  { id, modo, etiqueta, creada_en, score: int,
            eventos: [ { id, tipo, severidad, ts_cliente, ts_backend,
                         payload, screenshot_base64, screenshot_sha256,
                         face_count_cliente, face_count_servidor,
                         veredicto_reinferencia } ],
            biometria: { liveness_ok, retos_resueltos, resultado, registrada_en } | null }

GET    /api/v1/proctoring/health
  → 200  { status: 'ok', db: 'ok'|'error' }
```

## Dockerfile.slim y Railway

```dockerfile
FROM python:3.12-slim
WORKDIR /app
# mediapipe puede requerir libs nativas mínimas (libgl ya no en headless; mediapipe trae sus binarios)
COPY backend/requirements.txt .
# requirements.txt incluye mediapipe para la re-inferencia server-side (mismo motor que el cliente)
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# Reusar el MISMO modelo .task que el cliente: copiarlo del frontend a backend/models/
COPY frontend/public/mediapipe/face_detector_short_range.task /app/models/face_detector_short_range.task
# Railway inyecta DATABASE_URL, FRONTEND_ORIGIN, PORT via env vars
ENV PYTHONPATH=/app
ENV MEDIAPIPE_MODEL_DIR=/app/models
CMD alembic -c alembic.ini upgrade slim@head && \
    uvicorn app.main_slim:app --host 0.0.0.0 --port ${PORT:-8000}
```

> El `COPY` del `.task` requiere que el contexto de build sea la raíz del repo (`docker build -f Dockerfile.slim .`), de modo que `frontend/public/mediapipe/` sea accesible. El modelo viaja dentro de la imagen (no hay descarga en runtime). Si en el futuro el modelo se monta como volumen o se baja de un bucket, solo cambia `MEDIAPIPE_MODEL_DIR`.

Variables de entorno Railway:
| Variable | Requerida | Ejemplo |
|----------|-----------|---------|
| `DATABASE_URL` | Sí | `postgresql+asyncpg://user:pass@host:5432/db` |
| `FRONTEND_ORIGIN` | Sí | `https://activeexam.vercel.app` |
| `PORT` | Auto (Railway) | `8080` |
| `MEDIAPIPE_MODEL_DIR` | No (default `/app/models`) | `/app/models` |

## Risks / Trade-offs

- **Sin auth → datos expuestos**: Cualquiera con la URL accede al historial. Aceptable para demo; para producción agregar API key o JWT mínimo. [Riesgo] → Documentar en spec y README del deploy.
- **Screenshots en Postgres TEXT**: Rows grandes pueden degradar performance de `GET /sessions/{id}` con muchos eventos. [Riesgo] → Para producción mover a MinIO/S3 y guardar URL. En el demo el volumen es acotado.
- **Embedding sin cifrar en demo**: El embedding facial es dato sensible (Ley 25.326). [Riesgo] → Comentar en código `# PRODUCCION: cifrar con KMS antes de persistir; purgar al egreso`. El campo es nullable — se puede omitir en el demo.
- **Migration branch `slim` independiente**: Si alguien corre `alembic upgrade head` sin branch, puede intentar las migrations de producción (que requieren TimescaleDB). [Mitigación] → El Dockerfile.slim usa `alembic upgrade slim@head` explícitamente; documentar en el README.
- **`main_slim.py` separado de `main.py`**: Hay duplicación de setup de app. [Trade-off aceptado] → La separación es el punto: no cargar Keycloak/Vault/MinIO en el slim. Si en el futuro el módulo slim se integra a producción, se puede fusionar.
- **`mediapipe` es más pesado que OpenCV**: `mediapipe` + NumPy + binarios nativos suman bastante más que `opencv-python-headless` → imagen Docker más grande, más RAM en runtime y cold start más lento en Railway. [Trade-off aceptado] → Es el precio de la **consistencia de motor**: el cliente detecta con MediaPipe, así que el servidor debe usar el MISMO motor para que el veredicto `discrepancia` mida manipulación y no diferencias inter-motor. La precisión y defensibilidad del veredicto valen el peso extra. Si el cold start molesta en Railway, mitigar con instancia siempre-caliente o re-inferencia diferida (fuera de alcance demo).
- **Re-inferencia depende del modelo `.task` presente en runtime**: si el `.task` no llega al contenedor, no hay re-inferencia. [Riesgo] → El `Dockerfile.slim` lo copia del frontend en build; el adapter degrada a `no_evaluado` (RN-GLB-02) si falta, sin romper la ingesta. Verificar en deploy que `MEDIAPIPE_MODEL_DIR` apunte al modelo correcto.
- **Veredicto informativo, no sancionatorio**: MediaPipe sobre una screenshot estática puede igualmente dar falsos positivos/negativos de conteo (calidad de imagen, ángulo, oclusión). [Riesgo aceptado para demo] → El veredicto es informativo (L2.5: nunca sanciona); el revisor humano decide. Mitigación: degradación a `no_evaluado` ante error.
- **SHA-256 no es cadena de custodia**: detecta alteración básica pero no es firma encadenada ni WORM. [Trade-off aceptado] → Es integridad liviana de alcance demo; producción usa la cadena completa. Documentado en código.

## Migration Plan

1. Crear archivos del módulo slim (aditivo, sin tocar producción).
2. Crear `0005_proctoring_slim.py` con `branch_labels=("slim",)` y `depends_on=None`.
3. Crear `Dockerfile.slim`.
4. Deploy en Railway: conectar Postgres administrado, setear `DATABASE_URL` + `FRONTEND_ORIGIN`.
5. Railway ejecuta `alembic upgrade slim@head` al boot → crea las 3 tablas slim.
6. Uvicorn levanta en `$PORT`.
7. Rollback: `alembic downgrade slim@base` elimina las 3 tablas slim (sin afectar tablas de producción si coexisten).

## Open Questions

- ¿Railway provee Postgres con `asyncpg` disponible? (El driver async de SQLAlchemy). Alternativa: usar `psycopg2` síncrono si asyncpg da problemas en Railway — implicaría cambiar el engine slim a síncrono.
- ¿El demo necesita paginación en `GET /sessions`? Por ahora se devuelve todo (sin paginación); si el volumen crece agregar `limit`/`offset`.
- ¿Se necesita endpoint `PATCH /sessions/{id}/finalizar`? No está en el alcance inicial pero podría ser útil para marcar la sesión como finalizada desde el frontend.
- ¿De dónde sale `face_count_cliente`? Puede venir como campo explícito del body, derivarse del `payload` (ej. `payload.face_count`) o inferirse del `tipo` (`MULTIPLE_FACES` → ≥2, `FACE_ABSENT` → 0, presencia normal → 1). Hipótesis: aceptar `face_count_cliente` explícito y, si falta, derivarlo del `tipo`. A confirmar con el contrato del frontend.
- ¿La re-inferencia corre síncrona en el request o en background? Hipótesis demo: síncrona dentro de `POST /events`. OJO: MediaPipe puede ser más lento que OpenCV y el cold start del primer request (carga del modelo) puede notarse en Railway. Si la latencia molesta, cargar el `FaceDetector` una sola vez al boot (singleton en el adapter) y/o mover a tarea diferida (fuera de alcance demo).
- ¿El `FaceDetector` de MediaPipe es thread-safe / reusable entre requests? Hipótesis: instanciar el detector una vez (singleton) y reusarlo; si MediaPipe no lo permite de forma concurrente, instanciar por request (más lento) o serializar el acceso. A confirmar en la implementación.
