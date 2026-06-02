"""Router principal del modulo slim de proctoring.

Agrega los 3 sub-routers (sessions, events, biometria) y el endpoint de health.
Se monta en main_slim.py bajo el prefijo /api/v1/proctoring.

La session_factory y el adapter de re-inferencia se inyectan desde main_slim.py
para mantener el modulo slim totalmente desacoplado de SlimSettings.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.proctoring.reinferencia import ReinferenciaPort
from app.presentation.api.v1.proctoring.biometria.router import create_biometria_router
from app.presentation.api.v1.proctoring.events.router import create_events_router
from app.presentation.api.v1.proctoring.sessions.router import create_sessions_router


def create_proctoring_router(
    session_factory: async_sessionmaker[AsyncSession],
    reinferencia: ReinferenciaPort,
) -> APIRouter:
    """Factory del router principal de proctoring.

    Args:
        session_factory: Factory de sesiones async de SQLAlchemy (slim engine).
        reinferencia: Adapter del puerto ReinferenciaPort (MediaPipeReinferencia).

    Returns:
        APIRouter con todos los endpoints montados.
    """
    router = APIRouter(tags=["proctoring-slim"])

    # --- Dependencias ---

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def get_reinferencia() -> ReinferenciaPort:
        return reinferencia

    # --- Health ---

    @router.get("/health", summary="Healthcheck del modulo slim")
    async def health() -> JSONResponse:
        """Verifica que el modulo slim esta vivo y puede conectarse a la DB."""
        db_status = "error"
        async with session_factory() as session:
            try:
                await session.execute(text("SELECT 1"))
                db_status = "ok"
            except Exception:  # noqa: BLE001
                db_status = "error"

        return JSONResponse({"status": "ok", "db": db_status})

    # --- Sub-routers ---

    sessions_router = create_sessions_router(get_db)
    router.include_router(sessions_router)

    events_router = create_events_router(get_db, get_reinferencia)
    router.include_router(events_router)

    biometria_router = create_biometria_router(get_db)
    router.include_router(biometria_router)

    return router
