"""Engine async y session factory para el modulo activeexam.

Usa ActiveExamSettings (no Settings de produccion) para evitar cargar Keycloak/Vault/
MinIO al arrancar en Railway. Se construye desde DATABASE_URL directamente.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Valores por defecto, pensados para el despliegue de HOY: un proceso uvicorn contra
# un Postgres con max_connections=100. 1 x 24 = 24, con margen de sobra.
#
# El default de SQLAlchemy (5+10=15) es demasiado chico: con cada request abriendo su
# propia sesion (session-per-request), una carga con >15 requests concurrentes a
# endpoints que tocan DB entra en cola por conexion con la CPU lejos de saturarse.
# Medido: a 150 estudiantes posteando eventos, p99 de POST /events subia a ~1,6 s con
# CPU en ~0,2 de 8 cores.
POOL_SIZE_DEFAULT = 12
MAX_OVERFLOW_DEFAULT = 12


def _entero_de_entorno(nombre: str, por_defecto: int) -> int:
    """Lee un entero positivo del entorno; cualquier basura cae al default.

    Una variable mal escrita no puede tumbar el arranque de la app: como mucho deja
    el dimensionado por defecto, y la guarda del arranque avisa si no entra.
    """
    crudo = os.getenv(nombre, "").strip()
    if not crudo:
        return por_defecto
    try:
        valor = int(crudo)
    except ValueError:
        return por_defecto
    return valor if valor > 0 else por_defecto


def create_activeexam_engine(
    database_url: str,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> AsyncEngine:
    """Crea el engine async desde el DATABASE_URL dado.

    El tamaño del pool sale de `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` cuando están, y si
    no de los defaults de arriba. Es configurable a propósito: el techo de conexiones
    es `procesos x (pool_size + max_overflow)` y depende de cómo se lanzó el server y
    de qué Postgres hay del otro lado, así que no puede vivir como un número fijo en
    el código. Ya pasó una vez: 30+30 por worker con 4 workers dio 240 contra un
    `max_connections=100`, Postgres empezó a rechazar y el 503 escondía la causa.

    `dimensionado_pool.verificar_pool_configurado` corre al arrancar y avisa, con los
    números concretos, si lo configurado no entra en la base.
    """
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        pool_size=(
            pool_size
            if pool_size is not None
            else _entero_de_entorno("DB_POOL_SIZE", POOL_SIZE_DEFAULT)
        ),
        max_overflow=(
            max_overflow
            if max_overflow is not None
            else _entero_de_entorno("DB_MAX_OVERFLOW", MAX_OVERFLOW_DEFAULT)
        ),
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
