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
    """Crea el engine async desde el DATABASE_URL dado (ya leido de ActiveExamSettings).

    `pool_size`/`max_overflow` explicitos: el default de SQLAlchemy es 5+10=15
    conexiones concurrentes MAXIMO. Con una sola instancia uvicorn sirviendo REST
    (sin WS/SSE) y cada request abriendo su propia sesion (patron
    session-per-request), una prueba de carga con >15 requests concurrentes a
    endpoints que tocan DB entra en cola por conexion — con la CPU del proceso
    lejos de saturarse. Medido: a 150 estudiantes concurrentes posteando eventos,
    p99 de POST /events subia a ~1.6s con CPU en ~0.2 de 8 cores disponibles.

    12+12=24 por PROCESO (no por app): con `--workers N` cada worker es un
    proceso separado con su PROPIO engine/pool, asi que el maximo teorico de
    conexiones es N * 24. Con N=4 -> 96, bajo el default de Postgres
    (max_connections=100, con margen para conexiones de superusuario/admin).
    Un valor mas alto (30+30 por worker) agoto Postgres bajo carga real
    (4 * 60 = 240 > 100) y el 503 resultante ocultaba la causa real (ver el
    logging agregado en session_service.py::crear_o_reanudar_sesion).
    """
    return create_async_engine(
        database_url, pool_pre_ping=True, future=True, pool_size=12, max_overflow=12
    )


def create_activeexam_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Devuelve la factory de sesiones async ligada al engine activeexam."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_activeexam_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context async que abre una sesion y la cierra al salir."""
    async with factory() as session:
        yield session
