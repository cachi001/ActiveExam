"""1.3 RED → 1.4 GREEN → 1.5 TRIANGULATE: tests de repositorio contra DB real.

Requieren DATABASE_URL seteada. Sin ella, se saltan.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401 - registra tablas
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

_NEW_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


def _examen_con_preguntas() -> ExamenContenido:
    return ExamenContenido(
        titulo="Parcial Álgebra",
        preguntas=(
            Pregunta(
                enunciado="¿Capital de Francia?",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(texto="París", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="Madrid", es_correcta=False, orden=1),
                    OpcionRespuesta(texto="Roma", es_correcta=False, orden=2),
                ),
            ),
            Pregunta(
                enunciado="El Sol es una estrella.",
                tipo="truefalse",
                orden=1,
                opciones=(
                    OpcionRespuesta(texto="Verdadero", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="Falso", es_correcta=False, orden=1),
                ),
            ),
        ),
        comision_id=None,  # D11: nullable
    )


# ---------------------------------------------------------------------------
# 1.3 RED — tests de repositorio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardar_y_recuperar_examen(session):
    """Guarda un examen con preguntas/opciones y lo recupera completo."""
    repo = ExamenContenidoSqlRepository(session)
    examen = _examen_con_preguntas()

    guardado = await repo.guardar(examen)
    assert guardado.id is not None

    recuperado = await repo.obtener(guardado.id)
    assert recuperado is not None
    assert recuperado.titulo == "Parcial Álgebra"
    assert len(recuperado.preguntas) == 2
    assert recuperado.comision_id is None  # D11


@pytest.mark.asyncio
async def test_es_correcta_se_preserva_server_side(session):
    """es_correcta se persiste y se recupera correctamente (D3: nunca al cliente)."""
    repo = ExamenContenidoSqlRepository(session)
    examen = _examen_con_preguntas()

    guardado = await repo.guardar(examen)
    recuperado = await repo.obtener(guardado.id)
    assert recuperado is not None

    mc = next(p for p in recuperado.preguntas if p.tipo == "multichoice")
    correctas = [o for o in mc.opciones if o.es_correcta]
    assert len(correctas) == 1
    assert correctas[0].texto == "París"


@pytest.mark.asyncio
async def test_examen_no_encontrado_devuelve_none(session):
    """obtener con id inexistente devuelve None."""
    repo = ExamenContenidoSqlRepository(session)
    result = await repo.obtener("00000000-0000-0000-0000-000000000000")
    assert result is None


# ---------------------------------------------------------------------------
# 1.5 TRIANGULATE — reversibilidad: las tablas se crean y dropean
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tablas_existen_tras_create(engine):
    """Tras el setup del engine, las tres tablas existen en la DB."""
    async with engine.begin() as conn:
        for table_name in _NEW_TABLES:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = :name AND table_schema = 'public'"
                ),
                {"name": table_name},
            )
            assert result.scalar() == 1, f"Tabla {table_name!r} no existe"
