"""Fixtures compartidas para los tests del modulo slim de proctoring.

Los tests de integracion (requires_db_real) usan Postgres real/efimero.
Sin mocks de DB (regla dura de codigo: mockear la DB invalida el test).

Para correr los tests de integracion:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/ -v

Los tests unitarios (scoring, integridad, reinferencia sin DB) corren sin env vars.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.persistence.models.proctoring import (  # noqa: F401 -- registra tablas
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.base import Base


def _get_test_db_url() -> str | None:
    """Devuelve DATABASE_URL del entorno para tests (None si no esta seteada)."""
    return os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _get_test_db_url()
    if not url:
        pytest.skip(
            "DATABASE_URL no esta seteada. "
            "Para tests de integracion: DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/"
        )
    return url


_SLIM_TABLE_NAMES = (
    "proctoring_biometria",
    "proctoring_event",
    "proctoring_session",
)


@pytest_asyncio.fixture(scope="session")
async def slim_engine(db_url: str):
    """Engine async para los tests — usa Postgres real.

    Setup/teardown usan ``DROP TABLE ... CASCADE`` via SQL crudo: el ``table.drop``
    de SQLAlchemy emite ``DROP TABLE`` sin CASCADE, y falla si quedan vistas,
    triggers o referencias previas (cualquier estado sucio de una corrida anterior
    deja los tests rojos al iniciar).
    """
    engine = create_async_engine(db_url, pool_pre_ping=True, future=True)
    from app.infrastructure.persistence.models.proctoring import (  # noqa
        ProctoringBiometriaModel,
        ProctoringEventModel,
        ProctoringSessionModel,
    )
    slim_tables = [
        ProctoringSessionModel.__table__,
        ProctoringEventModel.__table__,
        ProctoringBiometriaModel.__table__,
    ]
    async with engine.begin() as conn:
        # Limpieza previa robusta (CASCADE) — tolera estado sucio de corridas previas.
        for name in _SLIM_TABLE_NAMES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        for table in slim_tables:
            await conn.run_sync(table.create, checkfirst=True)
    yield engine
    # Teardown final: idem, CASCADE para no dejar restos.
    async with engine.begin() as conn:
        for name in _SLIM_TABLE_NAMES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _limpiar_tablas_slim(engine) -> None:
    """Resetea las tablas slim. Usa TRUNCATE ... CASCADE (rapido y respeta FKs)."""
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{n}"' for n in _SLIM_TABLE_NAMES)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def db_session(slim_engine) -> AsyncIterator[AsyncSession]:
    """Sesion de DB para cada test — rollback al finalizar para aislar tests."""
    factory = async_sessionmaker(slim_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest.fixture
def slim_app(slim_engine):
    """App slim instanciada con el engine de test."""
    from app.infrastructure.persistence.session_slim import create_slim_session_factory
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia
    from app.presentation.api.v1.proctoring.router import create_proctoring_router
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    factory = create_slim_session_factory(slim_engine)
    reinferencia = MediaPipeReinferencia()
    proctoring_router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")
    return app


@pytest_asyncio.fixture
async def client(slim_app, slim_engine) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP async para tests de endpoints.

    Limpia las tablas slim ANTES de cada test para aislar estado entre tests
    (sin esto, las sesiones creadas en un test leakean al siguiente y los
    asserts dependen del orden de ejecucion)."""
    await _limpiar_tablas_slim(slim_engine)
    async with AsyncClient(
        transport=ASGITransport(app=slim_app), base_url="http://test"
    ) as c:
        yield c
