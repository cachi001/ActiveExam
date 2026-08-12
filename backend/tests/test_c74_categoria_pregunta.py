"""C-74 §1.5 RED→GREEN→TRIANGULATE: categorías del banco de preguntas contra DB real.

Cubre:
  - Crear categoría raíz y subcategoría (self-FK).
  - Listar árbol por materia.
  - Borrar categoría con preguntas → preguntas quedan con categoria_id=NULL (SET NULL).
  - Borrar categoría padre → subcategorías en cascada (ON DELETE CASCADE).

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

from app.domain.exam_content.entities import CategoriaPregunta
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.repositories.categoria_pregunta import (
    CategoriaPreguntaSqlRepository,
    CicloCategoriaError,
    MateriaDistintaError,
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


@pytest_asyncio.fixture
async def materia_id(session: AsyncSession) -> str:
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"MAT-{mid[:8]}", "n": "Materia Test C74"},
    )
    await session.commit()
    return mid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_categoria_raiz(session: AsyncSession, materia_id: str):
    """RED→GREEN: crea categoría raíz sin padre."""
    repo = CategoriaPreguntaSqlRepository(session)
    cat = await repo.crear(
        CategoriaPregunta(nombre="Unidad 1", materia_id=materia_id)
    )
    assert cat.id is not None
    assert cat.nombre == "Unidad 1"
    assert cat.categoria_padre_id is None


@pytest.mark.asyncio
async def test_crear_subcategoria(session: AsyncSession, materia_id: str):
    """TRIANGULATE: crea subcategoría con padre."""
    repo = CategoriaPreguntaSqlRepository(session)
    padre = await repo.crear(
        CategoriaPregunta(nombre="Unidad 2", materia_id=materia_id)
    )
    hijo = await repo.crear(
        CategoriaPregunta(nombre="Tema 2.1", materia_id=materia_id, categoria_padre_id=padre.id)
    )
    assert hijo.categoria_padre_id == padre.id


@pytest.mark.asyncio
async def test_listar_arbol_por_materia(session: AsyncSession, materia_id: str):
    """TRIANGULATE: listar_por_materia devuelve todas las categorías de la materia."""
    repo = CategoriaPreguntaSqlRepository(session)
    nombres_antes = {c.nombre for c in await repo.listar_por_materia(materia_id)}
    await repo.crear(CategoriaPregunta(nombre="Unidad 3", materia_id=materia_id))
    await repo.crear(CategoriaPregunta(nombre="Unidad 4", materia_id=materia_id))
    categorias = await repo.listar_por_materia(materia_id)
    nombres = {c.nombre for c in categorias}
    assert "Unidad 3" in nombres
    assert "Unidad 4" in nombres
    assert all(c.materia_id == materia_id for c in categorias)


@pytest.mark.asyncio
async def test_borrar_categoria_preguntas_quedan_sin_clasificar(
    session: AsyncSession, materia_id: str
):
    """TRIANGULATE: borrar categoría → preguntas quedan con categoria_id=NULL (SET NULL)."""
    repo = CategoriaPreguntaSqlRepository(session)
    cat = await repo.crear(CategoriaPregunta(nombre="A borrar", materia_id=materia_id))

    # Crear examen + pregunta asociada a la categoría
    examen_id = str(uuid.uuid4())
    pregunta_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"
        ),
        {"id": examen_id, "t": "Examen test"},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, categoria_id)"
            " VALUES (:id, :eid, :enunc, :tipo, :cid)"
        ),
        {
            "id": pregunta_id,
            "eid": examen_id,
            "enunc": "¿Qué es X?",
            "tipo": "multichoice",
            "cid": cat.id,
        },
    )
    await session.commit()

    # Borrar la categoría
    await repo.borrar(cat.id)
    await session.commit()

    # La pregunta sigue existiendo pero con categoria_id=NULL
    row = await session.execute(
        text("SELECT categoria_id FROM pregunta_examen WHERE id = :id"),
        {"id": pregunta_id},
    )
    result = row.fetchone()
    assert result is not None, "La pregunta no debe borrarse"
    assert result[0] is None, "categoria_id debe ser NULL tras borrar la categoría"


@pytest.mark.asyncio
async def test_borrar_padre_elimina_subcategorias_en_cascada(
    session: AsyncSession, materia_id: str
):
    """TRIANGULATE: borrar categoría padre → subcategorías borradas en cascada."""
    repo = CategoriaPreguntaSqlRepository(session)
    padre = await repo.crear(CategoriaPregunta(nombre="Padre cascade", materia_id=materia_id))
    hijo = await repo.crear(
        CategoriaPregunta(nombre="Hijo cascade", materia_id=materia_id, categoria_padre_id=padre.id)
    )
    await session.commit()

    await repo.borrar(padre.id)
    await session.commit()

    row = await session.execute(
        text("SELECT id FROM categoria_pregunta WHERE id = :id"),
        {"id": hijo.id},
    )
    assert row.fetchone() is None, "El hijo debe haberse borrado en cascada"


# ---------------------------------------------------------------------------
# Re-anidar (mover) una categoría bajo otro padre — drag&drop del banco.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mover_categoria_bajo_otro_padre(session: AsyncSession, materia_id: str):
    """RED→GREEN: mover una categoría raíz para que quede bajo otra."""
    repo = CategoriaPreguntaSqlRepository(session)
    destino = await repo.crear(CategoriaPregunta(nombre="Prog 1", materia_id=materia_id))
    suelta = await repo.crear(CategoriaPregunta(nombre="Manejo de errores", materia_id=materia_id))
    await session.commit()

    movida = await repo.mover(suelta.id, destino.id)

    assert movida.categoria_padre_id == destino.id
    recargada = await repo.obtener(suelta.id)
    assert recargada.categoria_padre_id == destino.id


@pytest.mark.asyncio
async def test_mover_categoria_a_raiz(session: AsyncSession, materia_id: str):
    """TRIANGULATE: mover a raíz (padre None) saca la categoría de su padre."""
    repo = CategoriaPreguntaSqlRepository(session)
    padre = await repo.crear(CategoriaPregunta(nombre="Padre", materia_id=materia_id))
    hijo = await repo.crear(
        CategoriaPregunta(nombre="Hijo", materia_id=materia_id, categoria_padre_id=padre.id)
    )
    await session.commit()

    movida = await repo.mover(hijo.id, None)

    assert movida.categoria_padre_id is None


@pytest.mark.asyncio
async def test_mover_categoria_a_si_misma_rechazado(session: AsyncSession, materia_id: str):
    """TRIANGULATE (edge): moverse a sí misma es un ciclo → CicloCategoriaError."""
    repo = CategoriaPreguntaSqlRepository(session)
    cat = await repo.crear(CategoriaPregunta(nombre="C", materia_id=materia_id))
    await session.commit()

    with pytest.raises(CicloCategoriaError):
        await repo.mover(cat.id, cat.id)


@pytest.mark.asyncio
async def test_mover_categoria_a_su_descendiente_rechazado(
    session: AsyncSession, materia_id: str
):
    """TRIANGULATE (edge): mover un ancestro dentro de su descendiente → ciclo."""
    repo = CategoriaPreguntaSqlRepository(session)
    abuelo = await repo.crear(CategoriaPregunta(nombre="Abuelo", materia_id=materia_id))
    padre = await repo.crear(
        CategoriaPregunta(nombre="Padre", materia_id=materia_id, categoria_padre_id=abuelo.id)
    )
    nieto = await repo.crear(
        CategoriaPregunta(nombre="Nieto", materia_id=materia_id, categoria_padre_id=padre.id)
    )
    await session.commit()

    with pytest.raises(CicloCategoriaError):
        await repo.mover(abuelo.id, nieto.id)


@pytest.mark.asyncio
async def test_mover_categoria_a_otra_materia_rechazado(session: AsyncSession, materia_id: str):
    """TRIANGULATE (edge): el destino debe ser de la misma materia."""
    repo = CategoriaPreguntaSqlRepository(session)
    otra_materia = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": otra_materia, "c": f"OTR-{otra_materia[:8]}", "n": "Otra materia"},
    )
    origen = await repo.crear(CategoriaPregunta(nombre="Origen", materia_id=materia_id))
    ajena = await repo.crear(CategoriaPregunta(nombre="Ajena", materia_id=otra_materia))
    await session.commit()

    with pytest.raises(MateriaDistintaError):
        await repo.mover(origen.id, ajena.id)
