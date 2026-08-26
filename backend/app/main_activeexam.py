"""Punto de entrada del modulo activeexam de proctoring + auth + biometria (c-57).

App factory sin Keycloak, Vault, MinIO, workers ni telemetria OTLP.
Solo necesita DATABASE_URL + FRONTEND_ORIGIN + JWT_OWN_SECRET +
EMBEDDING_ENCRYPTION_KEY + PORT (Railway 12-factor).

Arranca con:
    uvicorn app.main_activeexam:app --host 0.0.0.0 --port ${PORT:-8000}

En Railway el CMD del Dockerfile.activeexam corre primero:
    alembic upgrade activeexam@head && uvicorn app.main_activeexam:app ...

Routers montados:
    /api/v1/proctoring  - proctoring activeexam (sin auth — demo/PoC)
    /api/v1/auth        - login, refresh, /me (JWT HS256 propio)
    /api/v1/users       - creacion de usuarios (solo admin_sistema)
    /api/v1/enrollment  - foto de perfil (BYTEA en DB) + embedding cifrado
    /api/v1/consent     - consentimiento + via alternativa (C-63)
    /api/v1/scoring     - pesos por tipo de evento (#10, solo admin_sistema)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import DBAPIError

from app.infrastructure.persistence.uuid_errors import es_error_de_uuid_invalido
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config_activeexam import get_activeexam_settings, minio_configurado
from app.infrastructure.auth.activeexam_wiring import build_activeexam_jwt_validator
from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService
from app.infrastructure.crypto.evidence_encryption import EvidenceCipher
from app.application.moodle.credencial_docente_service import CredencialDocenteService
from app.application.moodle.credencial_service import MoodleCredencialResolver
from app.application.moodle.intentos_fallidos_tracker import IntentosFallidosTracker
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.moodle.wiring import build_writeback_svc_dinamico
from app.observability.metrics_activeexam import instrument_activeexam_metrics
from app.infrastructure.persistence.session_activeexam import (
    create_activeexam_engine,
    create_activeexam_session_factory,
)
from app.infrastructure.storage.db_photo_storage import DbPhotoStorageService
from app.presentation.api.v1.admin import admin_retention_router
from app.presentation.api.v1.auth.router import router as auth_router
from app.presentation.api.v1.dsr import dsr_activeexam_router
from app.presentation.api.v1.review import review_activeexam_router
from app.presentation.api.v1.verify_chain import verify_chain_activeexam_router
from app.presentation.api.v1.consent.dependencies import get_consent_service
from app.presentation.api.v1.consent.dependencies_activeexam import get_consent_service_activeexam
from app.application.config.service import ConfigService
from app.presentation.api.v1.config.router import router as config_router
from app.presentation.api.v1.consent.router import router as consent_router
from app.presentation.api.v1.consent_perfil.router import (
    router as consent_perfil_router,
)
from app.presentation.api.v1.enrollment.router import router as enrollment_router
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
    create_periodos_router,
)
from app.presentation.api.v1.lti import create_lti_router
from app.presentation.api.v1.proctoring.router import create_proctoring_router
from app.presentation.api.v1.scoring.router import router as scoring_router
from app.presentation.api.v1.users.router import router as users_router
from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

logger = logging.getLogger(__name__)

# Logging INFO minimo (twelve-factor: stdout). Sin esto, el logger de este modulo
# queda en el default WARNING de Python y el aviso de wiring de MinIO (c-77) nunca
# se ve. El stack completo (app/main.py) usa configure_logging con JSON+OTel; este
# modulo activeexam es deliberadamente liviano (sin OTel), asi que alcanza con
# basicConfig — no se justifica traer la dependencia de app.observability aca.
logging.basicConfig(level=logging.INFO)


def create_activeexam_app() -> FastAPI:
    """Factory de la app activeexam. No carga Keycloak, Vault, MinIO ni OTLP.

    Cablea en app.state (accedido por los routers de auth, users y enrollment):
      - settings: ActiveExamSettings (jwt_own_secret, jwt_audience, etc.)
      - jwt_validator: JwtValidator HS256-only (sin JWKS, sin Keycloak)
      - session_factory: async_sessionmaker para la DB activeexam
      - refresh_store: None (los routers usan DbRefreshTokenStore por request)
      - profile_photo_storage: DbPhotoStorageService (foto en BYTEA, sin MinIO)
      - embedding_encryption: EmbeddingEncryptionService con clave activeexam

    El ``refresh_store`` en app.state se deja en None porque el auth/router.py
    crea un ``DbRefreshTokenStore`` por request dentro de cada endpoint (patron
    session-per-request). El ``_get_refresh_store`` del router solo se llama en
    modo legacy (Keycloak/InMemory); en modo jwt con DB el router crea su propio
    DbStore inline — no necesita el state.
    """
    settings = get_activeexam_settings()

    # Engine y session factory del modulo activeexam (usa ActiveExamSettings, no Settings)
    engine: AsyncEngine = create_activeexam_engine(settings.database_url)
    session_factory: async_sessionmaker[AsyncSession] = create_activeexam_session_factory(engine)

    # Adapter de re-inferencia (singleton cargado al construir la app)
    reinferencia_adapter = MediaPipeReinferencia()

    # JwtValidator HS256-only (sin Keycloak, sin JWKS fetch) — OQ-1 resuelto.
    jwt_validator = build_activeexam_jwt_validator(settings)

    # Storage de foto de perfil en DB BYTEA (sin MinIO) — D1 design.
    profile_photo_storage = DbPhotoStorageService()

    # Servicio de cifrado de embeddings con clave activeexam (sin cargar Settings del full).
    embedding_encryption = EmbeddingEncryptionService(_key=settings.embedding_encryption_key)
    # Cifrado at-rest de la evidencia (screenshots) — MISMA clave, dato sensible
    # Ley 25.326 / regla #7. Antes se guardaba en claro.
    evidence_encryption = EvidenceCipher(key=settings.embedding_encryption_key)

    # Credencial de servicio de Moodle (migración 0047): vive en la base con el
    # token CIFRADO y la administra el admin del sistema. Mientras la tabla esté
    # vacía se cae a las variables de entorno (MOODLE_*), así que un despliegue
    # existente no cambia de comportamiento.
    _moodle_credenciales = MoodleCredencialResolver(
        session_factory=session_factory,
        cipher=SecretCipher(key=settings.embedding_encryption_key),
        env_base_url=settings.moodle_base_url,
        env_token=settings.moodle_ws_token,
        env_component=settings.moodle_component,
    )

    # Credencial PERSONAL de cada docente (C-73 §10, migración 0050). Es la vía
    # principal del write-back: la nota se devuelve con la identidad del docente a
    # cargo de la comisión. La institucional de arriba queda como respaldo.
    _credencial_docente = CredencialDocenteService(
        session_factory=session_factory,
        cipher=SecretCipher(key=settings.embedding_encryption_key),
    )

    # Contador en memoria de intentos fallidos de conexión (C-73, seguridad):
    # avisa si alguien prueba varias contraseñas seguidas contra la cuenta de
    # un docente. En memoria a propósito (ver docstring del módulo) — no es un
    # registro forense, es una señal de patrón sospechoso reciente.
    _intentos_fallidos_docentes = IntentosFallidosTracker()

    # Servicio de write-back de nota a Moodle (C-69, D7/D10).
    # La credencial se resuelve en CADA llamada: rotar el token desde la UI toma
    # efecto sin reiniciar. Si no hay credencial, el propio push falla y la nota
    # queda 'pendiente' (mismo camino que un fallo de red) — la finalización del
    # examen nunca se bloquea por Moodle.
    _writeback_svc = build_writeback_svc_dinamico(
        _moodle_credenciales, credencial_docente=_credencial_docente
    )

    # Config del Sistema (C-76 bloque 4): instancia UNICA compartida entre el
    # router de config (que la invalida al editar) y el de chat/pausa (que lee
    # ``pausas_max_por_sesion`` al aprobar). Sin compartir la instancia, editar el
    # limite desde /api/v1/config no se veria reflejado hasta reiniciar el proceso.
    _config_service = ConfigService(session_factory)

    # Bucket WORM de evidencia (c-77): ADICIONAL y opcional. MinIO no esta
    # disponible en Render hoy (sin VPS todavia) — el arranque de la app JAMAS
    # depende de esto (mismo patron tolerante try/except que app/main.py usa para
    # presign_service). Si las 4 variables MINIO_* no estan TODAS presentes,
    # _worm_storage queda en None y event_service sigue escribiendo SOLO en
    # Postgres, exactamente como antes de este change.
    _worm_storage = None
    if minio_configurado(settings):
        try:
            from app.infrastructure.storage.worm import build_boto3_worm_storage

            _worm_storage = build_boto3_worm_storage(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket_evidencia,
                use_ssl=settings.minio_use_ssl,
            )
            logger.info(
                "worm_storage: MinIO configurado — evidencia se deposita ADEMAS "
                "en el bucket WORM (endpoint=%s, bucket=%s).",
                settings.minio_endpoint,
                settings.minio_bucket_evidencia,
            )
        except Exception:  # noqa: BLE001 - MinIO no debe tumbar el arranque nunca
            logger.exception(
                "worm_storage: MinIO configurado pero fallo la construccion del "
                "cliente; evidencia queda solo en Postgres (temporal hasta VPS)."
            )
            _worm_storage = None
    else:
        logger.info(
            "worm_storage: MinIO no configurado — evidencia solo en DB, "
            "temporal hasta VPS."
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Cablear el state antes de empezar a servir requests.
        app.state.settings = settings
        app.state.jwt_validator = jwt_validator
        app.state.session_factory = session_factory
        app.state.refresh_store = None   # No-op: auth/router.py crea DbStore por request.
        app.state.profile_photo_storage = profile_photo_storage
        app.state.embedding_encryption = embedding_encryption
        # c-78: verify-chain y el informe de devolución tienen que DESCIFRAR la
        # captura antes de re-hashearla. Sin esto comparaban el hash del cifrado
        # contra el hash del claro y daban "cadena rota" en todos los eventos.
        app.state.evidence_encryption = evidence_encryption
        # El router de review es global (no se construye por factory), asi que toma
        # el write-back del state: lo necesita para el hook c-18 — anular por fraude
        # debe escribir el 0 en la libreta de Moodle. None = Moodle sin configurar.
        app.state.writeback_svc = _writeback_svc
        # El router de configuración lo usa para leer/guardar la credencial y para
        # invalidar el cache cuando el admin la cambia.
        app.state.moodle_credenciales = _moodle_credenciales
        # C-73 §10: credencial personal del docente (la vía principal del write-back).
        app.state.credencial_docente = _credencial_docente
        # C-73 §13: contador de intentos fallidos (en memoria, ver arriba).
        app.state.moodle_intentos_fallidos = _intentos_fallidos_docentes
        # C-76 bloque 4: instancia compartida — ver comentario arriba.
        app.state.config_service = _config_service
        # C-77: bucket WORM opcional — None si MinIO no esta configurado (ver
        # comentario arriba). Se expone tambien en el state por si otro modulo
        # (worker de re-verificacion, admin) lo necesita mas adelante.
        app.state.worm_storage = _worm_storage

        # c-78 §10.2: la allowlist LTI es la raiz de confianza del flujo. Si queda
        # SIN ninguna fila activa (tipico despues de recrear la base), ningun launch
        # entra y hoy la unica senal es un alumno que no puede rendir. Se avisa al
        # arranque, fuerte y temprano. Best-effort: nunca impide levantar la app.
        try:
            from app.application.lti.dynamic_registration import hay_deployment_activo

            async with session_factory() as _sesion_salud:
                if not await hay_deployment_activo(_sesion_salud):
                    logging.getLogger("lti").warning(
                        "ALLOWLIST LTI VACIA: no hay ningun deployment ACTIVO en "
                        "lti_deployment_confiable. Todo launch desde Moodle va a "
                        "responder 403 'lti_iss_no_confiable'. Registra la herramienta "
                        "desde Moodle (registro dinamico) y habilitala en "
                        "Administracion > Integracion LTI."
                    )
        except Exception:  # noqa: BLE001 — un chequeo de salud no tumba el arranque
            logging.getLogger("lti").debug(
                "No se pudo verificar la allowlist LTI al arranque.", exc_info=True
            )

        # c-78 §16.2: el pool se dimensionó para 4 workers con una cuenta escrita a
        # mano. Cambiar el plan, subir WEB_CONCURRENCY o mover la base deja esa cuenta
        # vieja, y el modo en que eso se manifiesta es Postgres rechazando conexiones
        # bajo carga con la app respondiendo 503 sin decir por qué. Se compara contra
        # el `max_connections` REAL de la base y se avisa acá, al arrancar, con los
        # números que hay que poner. Best-effort: nunca impide levantar la app.
        try:
            from sqlalchemy import text

            from app.infrastructure.persistence.dimensionado_pool import (
                contar_workers,
                dimensionar_pool,
                verificar_pool_configurado,
            )

            log_pool = logging.getLogger("pool")
            async with engine.connect() as _conn:
                _max_conn = int(
                    (await _conn.execute(text("SHOW max_connections"))).scalar_one()
                )
            # `uvicorn --workers N` no setea ninguna variable: hay que contar los
            # procesos de verdad o la cuenta sale mal por un factor de N.
            _workers = contar_workers()
            _pool = engine.pool
            _configurado = (_pool.size(), _pool._max_overflow)  # noqa: SLF001

            _problema = verificar_pool_configurado(
                workers=_workers,
                pool_size=_configurado[0],
                max_overflow=_configurado[1],
                max_connections=_max_conn,
            )
            if _problema:
                _sugerido = dimensionar_pool(_workers, _max_conn)
                log_pool.warning(
                    "POOL DE CONEXIONES MAL DIMENSIONADO. %s Para %d worker(s) contra "
                    "esta base: DB_POOL_SIZE=%d, DB_MAX_OVERFLOW=%d.",
                    _problema,
                    _workers,
                    _sugerido.pool_size,
                    _sugerido.max_overflow,
                )
            else:
                log_pool.info(
                    "Pool OK: %d worker(s) x %d conexiones = %d como máximo, sobre "
                    "max_connections=%d.",
                    _workers,
                    _configurado[0] + _configurado[1],
                    (_configurado[0] + _configurado[1]) * max(_workers, 1),
                    _max_conn,
                )
        except Exception:  # noqa: BLE001 — un chequeo de salud no tumba el arranque
            logging.getLogger("pool").debug(
                "No se pudo verificar el dimensionado del pool al arranque.",
                exc_info=True,
            )

        yield
        await engine.dispose()

    app = FastAPI(
        title="ActiveExam ActiveExam API",
        description=(
            "Modulo activeexam deployable en Railway — proctoring + auth JWT propia + "
            "enrollment biometrico. Sin Keycloak, Vault, MinIO ni TimescaleDB. "
            "Demo/PoC; para produccion completa usar main.py con la pila enterprise."
        ),
        version="0.2.0",
        docs_url="/api/v1/proctoring/docs",
        redoc_url="/api/v1/proctoring/redoc",
        lifespan=lifespan,
    )

    # CORS: FRONTEND_ORIGIN (Vercel) + localhost:5173 (dev local)
    allowed_origins = [settings.frontend_origin, "http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Un id de path que no es UUID responde 404, no 500 (c-78).
    #
    # Encontrado recorriendo produccion el 26/8/2026: `/exam-content/banco/preguntas`
    # (una ruta que no existe) matcheaba `/{examen_id}/preguntas` con
    # examen_id="banco", Postgres rechazaba el literal al compararlo contra una
    # columna uuid, y salia como 500. Pasaba en TODOS los endpoints con id en el
    # path: examen, sesion, usuario, y tambien en los nuevos.
    #
    # Va aca y no endpoint por endpoint a proposito: son decenas, y el que se
    # agregue manana volveria a fallar igual. Un id malformado significa lo mismo
    # que "no existe" — y devolver 500 hace pensar que se rompio el servidor
    # cuando el pedido era invalido, ademas de ensuciar las metricas de error.
    @app.exception_handler(DBAPIError)
    async def _id_malformado_es_404(_request: Request, exc: DBAPIError):
        if es_error_de_uuid_invalido(exc):
            # Se LOGUEA antes de convertirlo. Sin esto el handler tapa bugs
            # reales: un id mal armado por el propio backend sale como un 404
            # prolijo y nadie se entera de que algo lo genero mal.
            logger.warning(
                "id invalido en %s %s: %s",
                _request.method,
                _request.url.path,
                str(getattr(exc, "orig", exc))[:300],
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": {"error": "no_encontrado", "mensaje": "No existe."}},
            )
        raise exc

    # Metricas Prometheus (latencia + throughput HTTP + CPU/memoria de proceso).
    # main_activeexam.py no tenia NINGUNA metrica expuesta antes de esto.
    instrument_activeexam_metrics(app)

    # --- Routers ---

    # Proctoring: sessions, events, biometria (demo stateless + C-59 stateful).
    # embedding_encryption se pasa para montar los endpoints C-59 server-side.
    # El router queda montado en /api/v1/proctoring.
    proctoring_router = create_proctoring_router(
        session_factory=session_factory,
        reinferencia=reinferencia_adapter,
        embedding_encryption=embedding_encryption,
        writeback_svc=_writeback_svc,
        evidence_encryption=evidence_encryption,
        config_service=_config_service,
        worm_storage=_worm_storage,
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")

    # Auth JWT propio (c-55/c-57): login, refresh, /me
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    # Users (c-55/c-57): creacion de usuarios (solo admin_sistema)
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

    # Enrollment biometrico (c-56/c-57): foto (BYTEA) + embedding cifrado
    app.include_router(enrollment_router, prefix="/api/v1/enrollment", tags=["enrollment"])

    # Consentimiento (C-63): via alternativa + habilitacion por proctor.
    # Usamos dependency_override para inyectar el servicio activeexam (sin tabla consentimiento).
    app.dependency_overrides[get_consent_service] = get_consent_service_activeexam
    app.include_router(consent_router, prefix="/api/v1/consent", tags=["consent"])

    # Consentimiento de PERFIL persistido server-side (Ley 25.326, GAP #2).
    # POST/GET/POST-revoke en /api/v1/consent/profile. Fuente de verdad en BD
    # (reemplaza el localStorage demo del frontend en ola 2).
    app.include_router(
        consent_perfil_router,
        prefix="/api/v1/consent/profile",
        tags=["consent-profile"],
    )

    # Scoring (#10): configuracion de pesos por tipo de evento (solo admin_sistema).
    # Reusa app.state.session_factory + jwt_validator (ya cableados); no necesita
    # servicio extra. El front (ScoringConfig.tsx) pega a /api/v1/scoring/config y
    # /api/v1/scoring/weights. Sin este include, ambos daban 404 en prod (estaba
    # cableado solo en app.main, no en el activeexam que corre en Railway).
    app.include_router(scoring_router, prefix="/api/v1/scoring", tags=["scoring"])

    # Config del Sistema (configuracion-sistema-funcional): config efectiva +
    # edicion admin_sistema-only con MFA. GET /api/v1/config/effective lo consumen
    # TEST DETECCION y el examen; PATCH /api/v1/config lo edita admin_sistema.
    app.include_router(config_router, prefix="/api/v1/config", tags=["config"])

    # Admin (#19): trigger manual del motor de retencion (admin_sistema-only).
    # POST /api/v1/admin/retention/session  -> aplica retencion de sesiones
    # POST /api/v1/admin/retention/biometric -> borra biometria al egreso
    app.include_router(
        admin_retention_router, prefix="/api/v1/admin", tags=["admin"]
    )

    # Verify-chain activeexam (#18): re-verifica integridad SHA-256 de screenshots.
    # POST /api/v1/evidence/{event_id}/verify-chain  -> certificado autoportante
    app.include_router(
        verify_chain_activeexam_router, prefix="/api/v1", tags=["verify-chain"]
    )

    # DSR activeexam (#17): derechos del titular Ley 25.326 (access/rect/erasure/portability).
    app.include_router(dsr_activeexam_router, prefix="/api/v1/dsr", tags=["dsr"])

    # Review activeexam (#16): decision terminal inmutable del revisor.
    # POST /api/v1/review/session/{id}/decide
    app.include_router(review_activeexam_router, prefix="/api/v1/review", tags=["review"])

    # Exam content (C-69): importacion Moodle XML (admin-only) + lectura de
    # examen para la rendicion del alumno (sin opcion correcta, D3).
    # POST /api/v1/exam-content/moodle-import  -> admin importa el banco
    # GET  /api/v1/exam-content/{examen_id}    -> alumno rinde (sin es_correcta)
    app.include_router(
        create_periodos_router(),
        prefix="/api/v1/exam-content",
        tags=["exam-content"],
    )
    app.include_router(
        create_exam_content_router(
            session_factory=session_factory,
            writeback_svc=_writeback_svc,
        ),
        prefix="/api/v1/exam-content",
        tags=["exam-content"],
    )
    app.include_router(
        create_exam_taking_router(
            session_factory=session_factory,
            writeback_svc=_writeback_svc,
        ),
        prefix="/api/v1/exam-content",
        tags=["exam-content"],
    )

    # Estadísticas institucionales (C-20 re-alcanzado): conteos + riesgo + distribución.
    from app.presentation.api.v1.stats.router import create_stats_router

    app.include_router(
        create_stats_router(session_factory=session_factory),
        prefix="/api/v1/stats",
        tags=["stats"],
    )

    from app.presentation.api.v1.admin.audit_router import create_audit_router

    app.include_router(
        create_audit_router(session_factory=session_factory),
        prefix="/api/v1/admin",
        tags=["audit"],
    )

    # LTI 1.3 Tool Provider (C-75): JWKS + registro dinámico + login OIDC + launch
    # + JIT provisioning + emisión de sesión (sección 5).
    # Endpoints PÚBLICOS (el flujo LTI ocurre antes de tener sesión). La confianza
    # viene de la allowlist `lti_deployment_confiable` y de la firma del id_token.
    # jwt_secret / jwt_issuer / jwt_audience: MISMO emisor que POST /auth/login
    # (design D4 — un launch LTI válido es prueba de identidad suficiente para
    # emitir el JWT de sesión sin pedir contraseña).
    app.include_router(
        create_lti_router(
            session_factory=session_factory,
            cipher=SecretCipher(key=settings.embedding_encryption_key),
            jwt_secret=settings.jwt_own_secret,
            jwt_issuer=settings.jwt_own_issuer,
            jwt_audience=settings.jwt_audience,
            jwt_ttl_seconds=settings.access_token_ttl_seconds,
            refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
            frontend_url=settings.frontend_origin,
        ),
        prefix="/api/v1/lti",
        tags=["lti"],
    )

    # Admin del allowlist LTI (C-75 sección 6): CRUD admin_sistema-only de
    # `lti_deployment_confiable` — la raíz de confianza del flujo LTI.
    from app.presentation.api.v1.admin import create_lti_admin_router

    app.include_router(
        create_lti_admin_router(session_factory=session_factory),
        prefix="/api/v1/admin",
        tags=["admin", "lti"],
    )

    return app


# Instancia de la app para uvicorn
app = create_activeexam_app()
