"""Punto de entrada del modulo slim de proctoring.

App factory sin Keycloak, Vault, MinIO, workers ni telemetria OTLP.
Solo necesita DATABASE_URL + FRONTEND_ORIGIN + PORT (Railway 12-factor).

Arranca con:
    uvicorn app.main_slim:app --host 0.0.0.0 --port ${PORT:-8000}

En Railway el CMD del Dockerfile.slim corre primero:
    alembic upgrade slim@head && uvicorn app.main_slim:app ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

from app.config_slim import get_slim_settings
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)
from app.presentation.api.v1.proctoring.router import create_proctoring_router
from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia


def create_slim_app() -> FastAPI:
    """Factory de la app slim. No carga Keycloak, Vault, MinIO ni OTLP."""
    settings = get_slim_settings()

    # Engine y session factory del modulo slim (usa SlimSettings, no Settings)
    engine: AsyncEngine = create_slim_engine(settings.database_url)
    session_factory: async_sessionmaker[AsyncSession] = create_slim_session_factory(engine)

    # Adapter de re-inferencia (singleton cargado al construir la app)
    reinferencia_adapter = MediaPipeReinferencia()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title="ActiveExam Proctoring Slim API",
        description=(
            "Modulo slim de proctoring — REST sin auth, deployable en Railway. "
            "Demo/PoC; para produccion usar la pila completa con Keycloak/Vault/MinIO."
        ),
        version="0.1.0",
        docs_url="/api/v1/proctoring/docs",
        redoc_url="/api/v1/proctoring/redoc",
        lifespan=lifespan,
    )

    # CORS: FRONTEND_ORIGIN (Vercel) + localhost:5173 (dev local)
    # D6: parametrizable por env sin redeployar
    allowed_origins = [settings.frontend_origin, "http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Router slim — unico prefijo montado: /api/v1/proctoring
    proctoring_router = create_proctoring_router(
        session_factory=session_factory,
        reinferencia=reinferencia_adapter,
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")

    return app


# Instancia de la app para uvicorn
app = create_slim_app()
