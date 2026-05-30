"""Engine async y session factory de SQLAlchemy (infraestructura).

La conexion se toma de ``DATABASE_URL`` (twelve-factor, via Vault/tmpfs); NUNCA
se hardcodea. Driver async (asyncpg). El pool real lo usa la capa de aplicacion al
inyectar los repositorios. Esta pieza vive en infraestructura (puede acoplarse a
SQLAlchemy); el dominio nunca la importa.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def create_engine() -> AsyncEngine:
    """Crea el engine async desde ``DATABASE_URL`` (config por entorno)."""
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Devuelve la factory de sesiones async ligada al ``engine``."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context async que abre una sesion y la cierra al salir."""
    async with factory() as session:
        yield session
