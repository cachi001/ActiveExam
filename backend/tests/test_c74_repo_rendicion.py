"""C-74 Bugs B y C a nivel repositorio: lectura de examen para RENDIR.

Bug B: `obtener()` traía las N preguntas del pool (232 importadas para servir 20)
       y recién filtraba por `seleccionada` en Python. La rendición tardaba un
       montón en cargar preguntas y timer.
Bug C: `obtener()` no cargaba `pregunta_cloze_blank`, así que las cloze llegaban
       sin huecos.

`obtener_para_rendir()` filtra `seleccionada = true` EN SQL y hace eager load de
blanks y sus opciones.

Requieren DATABASE_URL seteada. Sin ella, se saltan.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

_TABLES = (
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
)


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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                PreguntaClozeBlankModel.__table__,
                OpcionClozeBlancoModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


async def _crear_examen_con_pool(session: AsyncSession) -> str:
    """Examen con 3 preguntas: 2 seleccionadas y 1 del pool sin seleccionar."""
    examen_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": f"Pool {examen_id[:8]}"},
    )
    for orden, seleccionada in enumerate((True, False, True)):
        pregunta_id = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada) "
                "VALUES (:id, :ex, :en, 'multichoice', :o, :sel)"
            ),
            {
                "id": pregunta_id,
                "ex": examen_id,
                "en": f"Pregunta {orden}",
                "o": orden,
                "sel": seleccionada,
            },
        )
        for i, correcta in enumerate((True, False)):
            await session.execute(
                text(
                    "INSERT INTO opcion_respuesta (id, pregunta_id, texto, es_correcta, orden) "
                    "VALUES (:id, :p, :t, :c, :o)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "p": pregunta_id,
                    "t": f"Opcion {i}",
                    "c": correcta,
                    "o": i,
                },
            )
    await session.commit()
    return examen_id


async def _crear_examen_cloze(session: AsyncSession) -> str:
    """Examen con una pregunta cloze de un blank MULTICHOICE con dos opciones."""
    examen_id = str(uuid.uuid4())
    pregunta_id = str(uuid.uuid4())
    blank_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": f"Cloze {examen_id[:8]}"},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada) "
            "VALUES (:id, :ex, :en, 'cloze', 0, true)"
        ),
        {"id": pregunta_id, "ex": examen_id, "en": "La funcion {1} cuenta."},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo, texto_antes, texto_despues) "
            "VALUES (:id, :p, 0, 'multichoice', 'La funcion ', ' cuenta.')"
        ),
        {"id": blank_id, "p": pregunta_id},
    )
    for texto, correcta in (("len", True), ("sum", False)):
        await session.execute(
            text(
                "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso) "
                "VALUES (:id, :b, :t, :c, 0)"
            ),
            {"id": str(uuid.uuid4()), "b": blank_id, "t": texto, "c": correcta},
        )
    await session.commit()
    return examen_id


# ---------------------------------------------------------------------------
# Bug B: filtro de seleccionadas en SQL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_para_rendir_solo_trae_seleccionadas(session: AsyncSession):
    """Bug B: las preguntas del pool sin seleccionar NO se traen de la DB."""
    examen_id = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    examen = await repo.obtener_para_rendir(examen_id)

    assert examen is not None
    assert len(examen.preguntas) == 2, "solo las 2 seleccionadas"
    assert all(p.seleccionada for p in examen.preguntas)
    assert [p.orden for p in examen.preguntas] == [0, 2]


@pytest.mark.asyncio
async def test_obtener_sigue_trayendo_todo_el_pool(session: AsyncSession):
    """Triangulación: `obtener()` (uso admin) sigue devolviendo el pool completo."""
    examen_id = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    examen = await repo.obtener(examen_id)

    assert examen is not None
    assert len(examen.preguntas) == 3


@pytest.mark.asyncio
async def test_obtener_para_rendir_examen_inexistente_devuelve_none(session: AsyncSession):
    """Borde: un id que no existe devuelve None, no explota."""
    repo = ExamenContenidoSqlRepository(session)
    assert await repo.obtener_para_rendir(str(uuid.uuid4())) is None


@pytest.mark.asyncio
async def test_obtener_para_rendir_conserva_opciones(session: AsyncSession):
    """Las opciones de las preguntas seleccionadas siguen viniendo completas."""
    examen_id = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    examen = await repo.obtener_para_rendir(examen_id)

    assert examen is not None
    for pregunta in examen.preguntas:
        assert len(pregunta.opciones) == 2


# ---------------------------------------------------------------------------
# Bug C: los blanks cloze se cargan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_para_rendir_carga_blanks_cloze(session: AsyncSession):
    """Bug C: la cloze trae sus huecos con texto alrededor y opciones."""
    examen_id = await _crear_examen_cloze(session)
    repo = ExamenContenidoSqlRepository(session)

    examen = await repo.obtener_para_rendir(examen_id)

    assert examen is not None
    pregunta = examen.preguntas[0]
    assert len(pregunta.blanks) == 1
    blank = pregunta.blanks[0]
    assert blank.tipo == "multichoice"
    assert blank.texto_antes == "La funcion "
    assert blank.texto_despues == " cuenta."
    assert {o.texto for o in blank.opciones} == {"len", "sum"}
    assert sum(1 for o in blank.opciones if o.es_correcta) == 1


@pytest.mark.asyncio
async def test_obtener_para_rendir_multichoice_sin_blanks(session: AsyncSession):
    """Triangulación: una multichoice normal viene con blanks vacío."""
    examen_id = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    examen = await repo.obtener_para_rendir(examen_id)

    assert examen is not None
    assert all(p.blanks == () for p in examen.preguntas)
