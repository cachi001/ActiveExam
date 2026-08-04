"""C-74 §2.1-2.5 RED→GREEN→TRIANGULATE: import XML Moodle con categorías.

Cubre:
  2.1 RED: documenta el bug actual — las preguntas importadas hoy no tienen
       categoria_ruta aunque el XML la provea.
  2.2-2.3 GREEN: el parser trackea el nodo category; el import_service
       persiste la jerarquía en categoria_pregunta.
  2.4 TRIANGULATE: segunda import del MISMO XML → idempotente (sin duplicados).
  2.5 TRIANGULATE: preguntas antes del primer nodo category → categoria_id=NULL.

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

from app.application.exam_content.moodle_parser import parse_moodle_xml
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)

_TABLES = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]

# --- XML de prueba con nodos category ---
XML_CON_CATEGORIAS = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>Pregunta U1 A</text></name>
    <questiontext format="html"><text>Enunciado A</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="multichoice">
    <name><text>Pregunta U1 B</text></name>
    <questiontext format="html"><text>Enunciado B</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="category">
    <category><text>$course$/top/Unidad 2/Tema 2.1</text></category>
  </question>
  <question type="multichoice">
    <name><text>Pregunta U2 A</text></name>
    <questiontext format="html"><text>Enunciado U2</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

# XML donde la primera pregunta no tiene categoría precedente
XML_SIN_CATEGORIA_INICIAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Pregunta sin categoria</text></name>
    <questiontext format="html"><text>Enunciado sin cat</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="category">
    <category><text>$course$/top/Unidad 3</text></category>
  </question>
  <question type="multichoice">
    <name><text>Pregunta con categoria</text></name>
    <questiontext format="html"><text>Enunciado con cat</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""


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
        {"id": mid, "c": f"CAT-{mid[:8]}", "n": "Materia Test Import"},
    )
    await session.commit()
    return mid


# ---------------------------------------------------------------------------
# Tests — parser (pure, no DB)
# ---------------------------------------------------------------------------


def test_2_1_parser_trackea_categoria_ruta():
    """2.1 RED → 2.2 GREEN: el parser devuelve categoria_ruta en cada pregunta."""
    result = parse_moodle_xml(XML_CON_CATEGORIAS)
    assert len(result.preguntas) == 3

    # Las dos primeras pertenecen a Unidad 1
    assert result.preguntas[0].categoria_ruta == ["Unidad 1"]
    assert result.preguntas[1].categoria_ruta == ["Unidad 1"]

    # La tercera a Unidad 2 → Tema 2.1
    assert result.preguntas[2].categoria_ruta == ["Unidad 2", "Tema 2.1"]


def test_2_5_pregunta_sin_categoria_inicial():
    """2.5 TRIANGULATE: pregunta antes del primer nodo category → categoria_ruta=None."""
    result = parse_moodle_xml(XML_SIN_CATEGORIA_INICIAL)
    assert len(result.preguntas) == 2
    assert result.preguntas[0].categoria_ruta is None  # sin categoría
    assert result.preguntas[1].categoria_ruta == ["Unidad 3"]


# ---------------------------------------------------------------------------
# Tests — import service (con DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_2_3_import_crea_jerarquia_categorias(session: AsyncSession, materia_id: str):
    """2.3 GREEN: import persiste jerarquía en categoria_pregunta y asigna categoria_id."""
    from app.application.exam_content.import_service import ImportacionMoodleService
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    repo = ExamenContenidoSqlRepository(session)
    svc = ImportacionMoodleService(repo)
    report = await svc.importar(
        XML_CON_CATEGORIAS,
        titulo="Test categorías",
        materia_id=materia_id,
    )
    await session.commit()

    assert report.importadas == 3

    # Verificar que las categorías se crearon
    cats = await session.execute(
        text("SELECT nombre, categoria_padre_id FROM categoria_pregunta WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    cats_rows = cats.fetchall()
    nombres = {r[0] for r in cats_rows}
    assert "Unidad 1" in nombres
    assert "Unidad 2" in nombres
    assert "Tema 2.1" in nombres

    # Verificar que las preguntas tienen categoria_id asignado
    pregs = await session.execute(
        text(
            "SELECT p.enunciado, c.nombre FROM pregunta_examen p"
            " LEFT JOIN categoria_pregunta c ON c.id = p.categoria_id"
            " WHERE p.examen_id = :eid"
        ),
        {"eid": report.examen_id},
    )
    rows = {r[0]: r[1] for r in pregs.fetchall()}
    assert rows.get("Enunciado A") == "Unidad 1"
    assert rows.get("Enunciado B") == "Unidad 1"
    assert rows.get("Enunciado U2") == "Tema 2.1"


@pytest.mark.asyncio
async def test_2_4_segunda_import_idempotente(session: AsyncSession, materia_id: str):
    """2.4 TRIANGULATE: segunda import del mismo XML → 0 categorías duplicadas."""
    from app.application.exam_content.import_service import ImportacionMoodleService
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    repo = ExamenContenidoSqlRepository(session)
    svc = ImportacionMoodleService(repo)

    # Primera import (puede ya existir de test anterior — ok si usa materia_id fresco)
    mid2 = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid2, "c": f"IDEM-{mid2[:8]}", "n": "Materia Idempotencia"},
    )
    await session.commit()

    await svc.importar(XML_CON_CATEGORIAS, titulo="Import 1", materia_id=mid2)
    await session.commit()

    await svc.importar(XML_CON_CATEGORIAS, titulo="Import 2", materia_id=mid2)
    await session.commit()

    cats = await session.execute(
        text(
            "SELECT nombre, COUNT(*) FROM categoria_pregunta"
            " WHERE materia_id = :mid GROUP BY nombre HAVING COUNT(*) > 1"
        ),
        {"mid": mid2},
    )
    duplicados = cats.fetchall()
    assert duplicados == [], f"Categorías duplicadas: {duplicados}"
