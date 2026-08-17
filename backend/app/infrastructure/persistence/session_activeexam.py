"""Engine async y session factory para el modulo activeexam.

Usa ActiveExamSettings (no Settings de produccion) para evitar cargar Keycloak/Vault/
MinIO al arrancar en Railway. Se construye desde DATABASE_URL directamente.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_activeexam_engine(database_url: str) -> AsyncEngine:
    """Crea el engine async desde el DATABASE_URL dado (ya leido de ActiveExamSettings)."""
    return create_async_engine(database_url, pool_pre_ping=True, future=True)


def create_activeexam_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Devuelve la factory de sesiones async ligada al engine activeexam."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_activeexam_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context async que abre una sesion y la cierra al salir."""
    async with factory() as session:
        yield session
