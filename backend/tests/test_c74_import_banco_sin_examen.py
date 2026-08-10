"""C-74: import de XML directo al banco de preguntas, SIN crear examen.

El import ligado a examen (`ImportacionMoodleService.importar`) siempre crea un
`examen_contenido` como efecto colateral, aunque se le pase `materia_id` para
poblar el banco. Eso está mal para el flujo real: primero se puebla el banco,
recién DESPUÉS (por separado) se arma un examen sorteando de ahí. Este test
cubre `importar_banco_desde_xml`, que puebla `pregunta_banco`/`categoria_pregunta`
sin tocar `examen_contenido` en absoluto.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.import_service import (
    SIN_CATEGORIA_SENTINEL,
    importar_banco_desde_xml,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    BlankBancoModel,
    CategoriaPreguntaModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionBlankBancoModel,
    PreguntaBancoModel,
)

_TABLES = [
    "opcion_blank_banco",
    "blank_banco",
    "opcion_banco",
    "pregunta_banco",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]

XML_DOS_PREGUNTAS = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>P1</text></name>
    <questiontext format="html"><text>Cuanto es dos mas dos</text></questiontext>
    <answer fraction="100"><text>Cuatro</text></answer>
    <answer fraction="0"><text>Cinco</text></answer>
  </question>
  <question type="multichoice">
    <name><text>P2</text></name>
    <questiontext format="html"><text>Cuanto es tres mas tres</text></questiontext>
    <answer fraction="100"><text>Seis</text></answer>
    <answer fraction="0"><text>Siete</text></answer>
  </question>
</quiz>
"""

# Dos categorías + una pregunta suelta sin categoría — para probar exclusión.
XML_DOS_CATEGORIAS = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Suelta</text></name>
    <questiontext format="html"><text>Sin categoria</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>U1-P1</text></name>
    <questiontext format="html"><text>Enunciado U1</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
  <question type="category">
    <category><text>$course$/top/Unidad 2</text></category>
  </question>
  <question type="multichoice">
    <name><text>U2-P1</text></name>
    <questiontext format="html"><text>Enunciado U2</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""

# Una pregunta multichoice inválida (0 correctas) — debe omitirse, no crashear.
XML_CON_INVALIDA = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Rota</text></name>
    <questiontext format="html"><text>Sin respuesta correcta</text></questiontext>
    <answer fraction="0"><text>A</text></answer>
    <answer fraction="0"><text>B</text></answer>
  </question>
  <question type="multichoice">
    <name><text>Buena</text></name>
    <questiontext format="html"><text>Enunciado valido</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>
"""


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
                PreguntaBancoModel.__table__,
                OpcionBancoModel.__table__,
                BlankBancoModel.__table__,
                OpcionBlankBancoModel.__table__,
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
        {"id": mid, "c": f"BANCO-{mid[:8]}", "n": "Materia Import Banco"},
    )
    await session.commit()
    return mid


@pytest.mark.asyncio
async def test_importa_al_banco_sin_crear_examen(session: AsyncSession, materia_id: str):
    """RED→GREEN: puebla pregunta_banco + categoria_pregunta, CERO examen_contenido."""
    report = await importar_banco_desde_xml(session, XML_DOS_PREGUNTAS, materia_id)
    await session.commit()

    assert report.preguntas_nuevas == 2
    assert report.preguntas_actualizadas == 0
    assert report.omitidas == []

    examenes = await session.execute(text("SELECT COUNT(*) FROM examen_contenido"))
    assert examenes.scalar_one() == 0, "el import al banco NO debe crear ningún examen"

    preguntas = await session.execute(
        text("SELECT enunciado FROM pregunta_banco WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    enunciados = {r[0] for r in preguntas.fetchall()}
    assert enunciados == {"Cuanto es dos mas dos", "Cuanto es tres mas tres"}

    cats = await session.execute(
        text("SELECT nombre FROM categoria_pregunta WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    assert {r[0] for r in cats.fetchall()} == {"Unidad 1"}


@pytest.mark.asyncio
async def test_reimport_actualiza_no_duplica(session: AsyncSession, materia_id: str):
    """TRIANGULATE: re-importar el mismo XML no duplica, marca como actualizadas."""
    await importar_banco_desde_xml(session, XML_DOS_PREGUNTAS, materia_id)
    await session.commit()

    report2 = await importar_banco_desde_xml(session, XML_DOS_PREGUNTAS, materia_id)
    await session.commit()

    assert report2.preguntas_nuevas == 0
    assert report2.preguntas_actualizadas == 2

    total = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_banco WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    assert total.scalar_one() == 2, "no debe duplicar en el re-import"


@pytest.mark.asyncio
async def test_pregunta_invalida_se_omite_sin_crashear(session: AsyncSession, materia_id: str):
    """TRIANGULATE: multichoice con 0 correctas se omite, la válida sí entra."""
    report = await importar_banco_desde_xml(session, XML_CON_INVALIDA, materia_id)
    await session.commit()

    assert report.preguntas_nuevas == 1
    assert len(report.omitidas) == 1
    assert report.omitidas[0].nombre.startswith("Sin respuesta correcta")

    preguntas = await session.execute(
        text("SELECT enunciado FROM pregunta_banco WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    assert {r[0] for r in preguntas.fetchall()} == {"Enunciado valido"}


# ---------------------------------------------------------------------------
# Exclusión de categorías: el docente puede destildar categorías en el
# preview antes de confirmar — esas preguntas NO deben entrar al banco.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluye_categoria_completa(session: AsyncSession, materia_id: str):
    """RED→GREEN: excluir ("Unidad 2",) deja fuera esa pregunta, el resto entra."""
    report = await importar_banco_desde_xml(
        session,
        XML_DOS_CATEGORIAS,
        materia_id,
        categorias_excluidas={("Unidad 2",)},
    )
    await session.commit()

    assert report.preguntas_nuevas == 2  # Suelta + U1-P1, no U2-P1
    enunciados = {p.enunciado for p in report.nuevas}
    assert enunciados == {"Sin categoria", "Enunciado U1"}

    en_db = await session.execute(
        text("SELECT enunciado FROM pregunta_banco WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    assert {r[0] for r in en_db.fetchall()} == {"Sin categoria", "Enunciado U1"}

    # La categoría "Unidad 2" tampoco se crea si todas sus preguntas se excluyeron.
    cats = await session.execute(
        text("SELECT nombre FROM categoria_pregunta WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    assert {r[0] for r in cats.fetchall()} == {"Unidad 1"}


@pytest.mark.asyncio
async def test_excluye_sin_categoria(session: AsyncSession, materia_id: str):
    """TRIANGULATE: el sentinel de 'sin categoría' excluye la pregunta suelta."""
    report = await importar_banco_desde_xml(
        session,
        XML_DOS_CATEGORIAS,
        materia_id,
        categorias_excluidas={SIN_CATEGORIA_SENTINEL},
    )
    await session.commit()

    assert report.preguntas_nuevas == 2  # U1-P1 + U2-P1, no la suelta
    enunciados = {p.enunciado for p in report.nuevas}
    assert enunciados == {"Enunciado U1", "Enunciado U2"}


@pytest.mark.asyncio
async def test_sin_exclusion_entra_todo(session: AsyncSession, materia_id: str):
    """Control: sin categorias_excluidas (o vacío), se comporta como siempre."""
    report = await importar_banco_desde_xml(
        session, XML_DOS_CATEGORIAS, materia_id, categorias_excluidas=None
    )
    await session.commit()

    assert report.preguntas_nuevas == 3
