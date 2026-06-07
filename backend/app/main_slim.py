"""Punto de entrada del modulo slim de proctoring + auth + biometria (c-57).

App factory sin Keycloak, Vault, MinIO, workers ni telemetria OTLP.
Solo necesita DATABASE_URL + FRONTEND_ORIGIN + JWT_OWN_SECRET +
EMBEDDING_ENCRYPTION_KEY + PORT (Railway 12-factor).

Arranca con:
    uvicorn app.main_slim:app --host 0.0.0.0 --port ${PORT:-8000}

En Railway el CMD del Dockerfile.slim corre primero:
    alembic upgrade slim@head && uvicorn app.main_slim:app ...

Routers montados:
    /api/v1/proctoring  - proctoring slim (sin auth — demo/PoC)
    /api/v1/auth        - login, refresh, /me (JWT HS256 propio)
    /api/v1/users       - creacion de usuarios (solo admin_sistema)
    /api/v1/enrollment  - foto de perfil (BYTEA en DB) + embedding cifrado
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config_slim import get_slim_settings
from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator
from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)
from app.infrastructure.storage.db_photo_storage import DbPhotoStorageService
from app.presentation.api.v1.auth.router import router as auth_router
from app.presentation.api.v1.enrollment.router import router as enrollment_router
from app.presentation.api.v1.proctoring.router import create_proctoring_router
from app.presentation.api.v1.users.router import router as users_router
from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia


def create_slim_app() -> FastAPI:
    """Factory de la app slim. No carga Keycloak, Vault, MinIO ni OTLP.

    Cablea en app.state (accedido por los routers de auth, users y enrollment):
      - settings: SlimSettings (jwt_own_secret, jwt_audience, etc.)
      - jwt_validator: JwtValidator HS256-only (sin JWKS, sin Keycloak)
      - session_factory: async_sessionmaker para la DB slim
      - refresh_store: None (los routers usan DbRefreshTokenStore por request)
      - profile_photo_storage: DbPhotoStorageService (foto en BYTEA, sin MinIO)
      - embedding_encryption: EmbeddingEncryptionService con clave slim

    El ``refresh_store`` en app.state se deja en None porque el auth/router.py
    crea un ``DbRefreshTokenStore`` por request dentro de cada endpoint (patron
    session-per-request). El ``_get_refresh_store`` del router solo se llama en
    modo legacy (Keycloak/InMemory); en modo jwt con DB el router crea su propio
    DbStore inline — no necesita el state.
    """
    settings = get_slim_settings()

    # Engine y session factory del modulo slim (usa SlimSettings, no Settings)
    engine: AsyncEngine = create_slim_engine(settings.database_url)
    session_factory: async_sessionmaker[AsyncSession] = create_slim_session_factory(engine)

    # Adapter de re-inferencia (singleton cargado al construir la app)
    reinferencia_adapter = MediaPipeReinferencia()

    # JwtValidator HS256-only (sin Keycloak, sin JWKS fetch) — OQ-1 resuelto.
    jwt_validator = build_slim_jwt_validator(settings)

    # Storage de foto de perfil en DB BYTEA (sin MinIO) — D1 design.
    profile_photo_storage = DbPhotoStorageService()

    # Servicio de cifrado de embeddings con clave slim (sin cargar Settings del full).
    embedding_encryption = EmbeddingEncryptionService(_key=settings.embedding_encryption_key)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Cablear el state antes de empezar a servir requests.
        app.state.settings = settings
        app.state.jwt_validator = jwt_validator
        app.state.session_factory = session_factory
        app.state.refresh_store = None   # No-op: auth/router.py crea DbStore por request.
        app.state.profile_photo_storage = profile_photo_storage
        app.state.embedding_encryption = embedding_encryption
        yield
        await engine.dispose()

    app = FastAPI(
        title="ActiveExam Slim API",
        description=(
            "Modulo slim deployable en Railway — proctoring + auth JWT propia + "
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

    # --- Routers ---

    # Proctoring: sessions, events, biometria (demo stateless + C-59 stateful).
    # embedding_encryption se pasa para montar los endpoints C-59 server-side.
    # El router queda montado en /api/v1/proctoring.
    proctoring_router = create_proctoring_router(
        session_factory=session_factory,
        reinferencia=reinferencia_adapter,
        embedding_encryption=embedding_encryption,
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")

    # Auth JWT propio (c-55/c-57): login, refresh, /me
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    # Users (c-55/c-57): creacion de usuarios (solo admin_sistema)
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

    # Enrollment biometrico (c-56/c-57): foto (BYTEA) + embedding cifrado
    app.include_router(enrollment_router, prefix="/api/v1/enrollment", tags=["enrollment"])

    return app


# Instancia de la app para uvicorn
app = create_slim_app()
