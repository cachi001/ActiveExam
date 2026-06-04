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
    #
    # PoC C-03 D10: si poc_jwt_secret esta seteado, se recablea el validador para
    # usar HS256 estatico (build_hs256_verify) en vez de JWKS/Keycloak. Esto
    # permite que k6 use tokens firmados con el secret conocido sin round-trip a
    # Keycloak (que se excluye del docker-compose.poc.yml). SOLO para el harness
    # descartable; en produccion poc_jwt_secret es None y el RS256 permanece.
    from app.infrastructure.auth.refresh_store import InMemoryRefreshTokenStore

    app.state.settings = settings

    if settings.poc_jwt_secret:
        # Modo sin-auth PoC: validator HS256 estatico (bypass de Keycloak).
        try:
            from app.domain.auth.token import TokenPolicy
            from app.infrastructure.auth.jwt_validator import JwtValidator
            from app.infrastructure.auth.jwks_cache import JwksCache
            from app.infrastructure.auth.verifiers import build_hs256_verify

            _secret_bytes = settings.poc_jwt_secret.encode("utf-8")
            # La JwksCache no se usa con HS256; inyectamos un stub que siempre
            # devuelve None (el verificador HS256 ignora el parametro jwk).
            _stub_cache = JwksCache(lambda: {"keys": []}, ttl_seconds=0)
            _hs256_policy = TokenPolicy(
                issuer=settings.keycloak_issuer,
                audience=settings.jwt_audience,
            )
            app.state.jwt_validator = JwtValidator(
                jwks_cache=_stub_cache,
                policy=_hs256_policy,
                verify_fn=build_hs256_verify(_secret_bytes),
            )
            logging.getLogger(__name__).warning(
                "PoC C-03: validador JWT recableado a HS256 estatico "
                "(poc_jwt_secret seteado). NO usar en produccion."
            )
        except Exception:  # noqa: BLE001
            app.state.jwt_validator = None
    else:
        # Modo produccion: RS256 + JWKS cacheado de Keycloak (C-06).
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

    # --- Backplane fan-out (PoC C-03 D9 — SOLO bajo poc_panel_enabled) ---------
    # El publisher asyncpg real ejecuta pg_notify(canal, payload) con una conexion
    # dedicada (separada del pool SQLAlchemy). La conexion asyncpg se abre al primer
    # publish (lazy) para no bloquear el arranque.
    #
    # AISLAMIENTO PoC/prod: este cableado se monta SOLO con poc_panel_enabled, igual
    # que el router SSE y las metricas. En PRODUCCION el fan-out queda no-op inerte
    # (backplane_publisher=None -> get_backplane usa un _noop): es C-10 quien cablea
    # el publisher real con lifecycle completo (pool supervisado, reconexion con
    # backoff, cierre ordenado). Adelantar el fan-out a prod sin flag dispararia
    # pg_notify al vacio (sin paneles SSE de C-15 escuchando) + 1 conexion extra.
    if settings.poc_panel_enabled:
        try:
            from app.infrastructure.messaging.asyncpg_publisher import AsyncpgPublisher
            from app.infrastructure.messaging.backplane import build_backplane

            _asyncpg_publisher = AsyncpgPublisher(dsn=settings.database_url)
            # Guardar la instancia completa (para .close() al shutdown) y el metodo
            # .publish como el callable Publisher que espera get_backplane en
            # dependencies.py (toma app.state.backplane_publisher como callable).
            app.state.backplane_publisher_instance = _asyncpg_publisher
            app.state.backplane_publisher = _asyncpg_publisher.publish
            app.state.backplane = build_backplane(
                settings.messaging_backend,
                _asyncpg_publisher.publish,
            )
        except Exception as exc:  # noqa: BLE001 - sin asyncpg el backplane queda no-op
            app.state.backplane_publisher_instance = None
            app.state.backplane_publisher = None
            app.state.backplane = None
            # PoC C-03: si el publisher cae a None, get_backplane usa un _noop y NINGUN
            # pg_notify se dispara — el fan-out queda inerte SIN error visible. En la PoC
            # eso significa medir un circuito muerto (k6 persiste eventos pero el panel
            # SSE no recibe nada). Por eso este except DEBE gritar (no tragar en silencio).
            logging.getLogger(__name__).warning(
                "PoC C-03: backplane fan-out NO cableado: el publisher asyncpg quedo "
                "en None (%s). El fan-out evento->panel sera no-op y la medicion del "
                "concern (c) sera invalida hasta resolverlo.",
                exc,
            )
    else:
        # Produccion (sin poc_panel_enabled): fan-out no-op inerte hasta C-10.
        app.state.backplane_publisher_instance = None
        app.state.backplane_publisher = None
        app.state.backplane = None

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

    # --- Router PoC C-03 (DESCARTABLE — montado solo si poc_panel_enabled) ------
    # Expone GET /poc/panel/stream?exam_id=X (SSE, asyncpg LISTEN/NOTIFY). Solo
    # cuando poc_panel_enabled=True; en produccion esta var es False -> no se monta.
    if settings.poc_panel_enabled:
        try:
            from app.presentation.api.v1.poc.panel_router import router as poc_panel_router

            # Importar el modulo registra las 3 metricas PoC en el REGISTRY default
            # (Bloque 2): aparecen en /metrics con valor 0 aunque no haya carga.
            from app.observability import poc_metrics  # noqa: F401

            app.include_router(poc_panel_router, prefix="/poc", tags=["poc-c03"])
            logging.getLogger(__name__).warning(
                "PoC C-03: router /poc/panel/stream montado + metricas PoC registradas "
                "(poc_panel_enabled=True). NO usar en produccion."
            )
        except Exception:  # noqa: BLE001 - si falla la importacion, no bloquea el arranque
            logging.getLogger(__name__).warning(
                "PoC C-03: no se pudo montar el router /poc/panel/stream."
            )

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

