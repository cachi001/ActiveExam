"""C-74 §3.1-3.5 RED→GREEN→TRIANGULATE: sorteo aleatorio de preguntas por categoría.

Cubre:
  3.5a sortear N de A + N de B → exactamente 2N seleccionadas, N/N.
  3.5b repetir antes de intento finalizado → nueva selección (no idempotente).
  3.5c sorteo cuando no hay suficientes preguntas → SorteoInsuficienteError (422).

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

from app.application.exam_content.errors import SorteoInsuficienteError
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

_TABLES = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]


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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                CategoriaPreguntaModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
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


async def _crear_examen_con_pool(session: AsyncSession) -> tuple[str, str, str]:
    """Crea materia + examen + 10 preguntas (5 cat_a, 5 cat_b).

    Devuelve (examen_id, cat_a_id, cat_b_id).
    """
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"S-{mid[:6]}", "n": "Materia Sorteo"},
    )

    cat_a_id = str(uuid.uuid4())
    cat_b_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre) VALUES "
            "(:id, :mid, :n)"
        ),
        {"id": cat_a_id, "mid": mid, "n": "Cat A"},
    )
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre) VALUES "
            "(:id, :mid, :n)"
        ),
        {"id": cat_b_id, "mid": mid, "n": "Cat B"},
    )

    examen_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": "Examen sorteo"},
    )

    # 5 preguntas de cat_a, 5 de cat_b
    for i in range(5):
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, categoria_id)"
                " VALUES (:id, :eid, :enunc, 'multichoice', :ord, :cid)"
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": examen_id,
                "enunc": f"Pregunta A-{i}",
                "ord": i,
                "cid": cat_a_id,
            },
        )
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, categoria_id)"
                " VALUES (:id, :eid, :enunc, 'multichoice', :ord, :cid)"
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": examen_id,
                "enunc": f"Pregunta B-{i}",
                "ord": 10 + i,
                "cid": cat_b_id,
            },
        )

    await session.commit()
    return examen_id, cat_a_id, cat_b_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_3_5a_sorteo_exactamente_n_por_categoria(session: AsyncSession):
    """3.5a GREEN: sortear 2 de A + 2 de B → 4 seleccionadas, 2/2."""
    examen_id, cat_a, cat_b = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    items = await repo.sortear_por_categorias(examen_id, [cat_a, cat_b], 2)
    await session.commit()

    assert items is not None
    seleccionadas = [p for p in items if p.seleccionada]
    no_seleccionadas = [p for p in items if not p.seleccionada]
    assert len(seleccionadas) == 4, f"Esperadas 4 seleccionadas, hay {len(seleccionadas)}"
    assert len(no_seleccionadas) == 6, "El resto debe quedar no seleccionado"

    # Verificar distribución: 2 de cat_a, 2 de cat_b
    sel_ids = {p.id for p in seleccionadas}
    rows = await session.execute(
        text(
            "SELECT categoria_id, COUNT(*) cnt FROM pregunta_examen"
            " WHERE id = ANY(:ids) GROUP BY categoria_id"
        ),
        {"ids": list(sel_ids)},
    )
    por_cat = {str(r[0]): r[1] for r in rows.fetchall()}
    assert por_cat.get(cat_a) == 2, f"Cat A: esperadas 2, hay {por_cat.get(cat_a)}"
    assert por_cat.get(cat_b) == 2, f"Cat B: esperadas 2, hay {por_cat.get(cat_b)}"


@pytest.mark.asyncio
async def test_3_5b_segunda_llamada_produce_seleccion_nueva(session: AsyncSession):
    """3.5b TRIANGULATE: el sorteo NO es idempotente — dos llamadas pueden dar resultados distintos."""
    examen_id, cat_a, cat_b = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    items1 = await repo.sortear_por_categorias(examen_id, [cat_a, cat_b], 3)
    await session.commit()
    sel1 = {p.id for p in items1 if p.seleccionada}  # type: ignore[union-attr]

    # El segundo sorteo puede dar el mismo resultado por azar, pero el estado persiste
    items2 = await repo.sortear_por_categorias(examen_id, [cat_a, cat_b], 3)
    await session.commit()
    sel2 = {p.id for p in items2 if p.seleccionada}  # type: ignore[union-attr]

    # Lo importante: siempre hay exactamente 6 seleccionadas tras cada sorteo
    assert len(sel1) == 6
    assert len(sel2) == 6
    # Y el estado en DB refleja el ÚLTIMO sorteo (sel1 ha sido reemplazado por sel2)
    db_rows = await session.execute(
        text("SELECT id FROM pregunta_examen WHERE examen_id=:eid AND seleccionada=true"),
        {"eid": examen_id},
    )
    sel_db = {str(r[0]) for r in db_rows.fetchall()}
    assert sel_db == sel2


@pytest.mark.asyncio
async def test_3_5c_sorteo_insuficiente_lanza_error(session: AsyncSession):
    """3.5c TRIANGULATE: pedir más preguntas que las disponibles → SorteoInsuficienteError."""
    examen_id, cat_a, cat_b = await _crear_examen_con_pool(session)
    repo = ExamenContenidoSqlRepository(session)

    with pytest.raises(SorteoInsuficienteError) as exc_info:
        await repo.sortear_por_categorias(examen_id, [cat_a], 10)  # solo hay 5

    assert exc_info.value.disponibles == 5
    assert exc_info.value.pedidas == 10
