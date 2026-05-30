"""App factory de la API de Proctoring (FastAPI / ASGI).

Ejecucion MONO-HILO (DD-10): cada instancia es un unico proceso uvicorn de un
hilo asincrono (NO multi-worker dentro de la instancia). El escalado es
HORIZONTAL detras de Nginx (1 instancia approx 1 pod). Ver
``infra/docker-compose`` + ``infra/nginx``.

Twelve-factor:
- Config 100% por entorno (``app.config.Settings``); falla al arrancar si falta.
- Logs estructurados JSON a stdout (recogidos por Loki).
- Sin estado local: cualquier instancia atiende cualquier request.

Observabilidad montada desde Fase 0 (DD-12): trazas OTLP a Tempo + ``/metrics``
Prometheus + ``trace_id`` en cada log.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Response

from app.config import Settings, get_settings
from app.observability.logging import configure_logging
from app.observability.telemetry import instrument_app, metrics_endpoint
from app.presentation.api.v1 import api_v1_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye y configura la instancia de FastAPI.

    Recibe ``settings`` por inyeccion (facilita los tests). Si es ``None``, los
    carga del entorno; si falta config requerida, ``Settings()`` falla aqui de
    forma explicita (twelve-factor, sin default inseguro).
    """
    settings = settings or get_settings()

    configure_logging(level=logging.INFO)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # --- Subsistema de auth (C-06) -------------------------------------------
    # El JwtValidator (JWKS cacheado + RS256) y el store de rotacion de refresh se
    # cablean en el app.state para que las dependencias los tomen sin que el
    # dominio dependa de FastAPI. La construccion del validador RS256 es perezosa:
    # si PyJWT no esta disponible (entorno sin la dep), el state queda en None y
    # las dependencias devuelven 500 explicito en vez de fallar al arrancar.
    from app.infrastructure.auth.refresh_store import InMemoryRefreshTokenStore

    app.state.settings = settings
    try:
        from app.infrastructure.auth.wiring import build_jwt_validator

        app.state.jwt_validator = build_jwt_validator(settings)
    except Exception:  # noqa: BLE001 - sin PyJWT/JWKS el validador no se arma aun
        app.state.jwt_validator = None
    app.state.refresh_store = InMemoryRefreshTokenStore()

    # --- Persistencia y storage (C-07 consume; cableado perezoso/tolerante) ---
    # session_factory para los routers de dominio (exams). Si el engine no se puede
    # crear (entorno sin DB), queda en None y las dependencias devuelven 500 explicito.
    try:
        from app.infrastructure.persistence.session import (
            create_engine,
            create_session_factory,
        )
        from app.infrastructure.storage.presign import StoragePresignService

        engine = create_engine()
        app.state.session_factory = create_session_factory(engine)
        app.state.presign_service = StoragePresignService(
            endpoint=settings.storage_endpoint,
            bucket=settings.storage_bucket_evidence,
        )
    except Exception:  # noqa: BLE001 - sin DB/driver el dominio no se cablea aun
        app.state.session_factory = None
        app.state.presign_service = None

    # --- Evidencia (C-12): bucket WORM (Object Lock Compliance) ----------------
    # El binario de evidencia se deposita/re-descarga en un bucket WORM. El SDK real
    # (boto3/minio con ObjectLockMode='COMPLIANCE') se inyecta en deploy via callables;
    # sin el, queda en None y las dependencias devuelven 500 explicito. La clave
    # maestra de firma (etapa 3) vive en Vault y NUNCA se hardcodea: el signer la
    # recibe inyectada en produccion.
    app.state.worm_storage = None
    app.state.master_signer = None

    # Cola de mensajeria (default A4: Postgres-como-cola). C-08 la usa para escalar
    # la via alternativa a un proctor; C-09 la usa para escalar la verificacion
    # biometrica al 3.º fallo; C-10 para el fan-out. El puerto queda cableado.
    try:
        from app.infrastructure.messaging.postgres_queue import PostgresMessageQueue

        app.state.message_queue = PostgresMessageQueue(settings.database_url)
    except Exception:  # noqa: BLE001
        app.state.message_queue = None

    # --- Biometria (C-09): motor de vision, KMS y secreto maestro ------------
    # El motor de vision server-side (re-inferencia, DD-17), el KMS de cifrado del
    # embedding (D5) y el proveedor del secreto maestro (Vault) se cablean en
    # produccion. Sin la libreria de vision o Vault inyectado, quedan en None y las
    # dependencias devuelven 500 explicito (twelve-factor, sin default inseguro).
    # NUNCA se hardcodea un secreto: el lector lo toma del entorno/Vault.
    try:
        from app.infrastructure.biometrics.wiring import build_biometrics_subsystem

        vision_engine, kms_cipher, secret_provider = build_biometrics_subsystem(settings)
        app.state.vision_engine = vision_engine
        app.state.kms_cipher = kms_cipher
        app.state.secret_provider = secret_provider
    except Exception:  # noqa: BLE001 - sin motor de vision / KMS no se cablea aun
        app.state.vision_engine = None
        app.state.kms_cipher = None
        app.state.secret_provider = None

    # Router base /api/v1 (healthchecks C-04; auth C-06; dominio C-05+).
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    # Endpoint de metricas Prometheus (scrapeado por Prometheus).
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        payload, content_type = metrics_endpoint()
        return Response(content=payload, media_type=content_type)

    # Instrumentacion OTLP (tolerante a la ausencia de OTel en tests).
    instrument_app(
        app,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        service_name=settings.otel_service_name,
    )

    return app


def __getattr__(name: str) -> object:
    """Construccion perezosa del objeto ASGI ``app`` para uvicorn.

    ``uvicorn app.main:app`` resuelve este atributo y dispara ``create_app()``,
    que carga la config del entorno (y falla explicito si falta). Hacerlo perezoso
    evita que el simple ``import app.main`` exija el entorno completo (los tests
    importan ``create_app`` e inyectan settings de prueba).

    Mono-hilo: arrancar SIN ``--workers >1``; el escalado es por instancias/Nginx.
    """
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

