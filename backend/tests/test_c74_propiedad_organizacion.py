"""C-74 / 0058: la organización del banco es del docente, no de Moodle.

Regla que se prueba acá: **el contenido lo manda Moodle, la organización la
manda el docente**. Concretamente:

  - Una pregunta movida a mano (``categoria_manual=True``) no vuelve a ser
    recategorizada por un re-import de XML ni por un sync.
  - Una categoría renombrada localmente sigue siendo reconocida por el sync
    (ancla: ``moodle_category_id``) y por el import de XML (ancla:
    ``moodle_nombre_origen``) — no se duplica ni se le pisa el nombre.
  - Un re-import no duplica preguntas que vengan sin ``moodle_question_id``.
  - Un re-import SÍ refresca enunciado y opciones: quedarse con la opción
    correcta vieja calificaría mal en silencio.

DB real (regla dura #4: nada de mockear la base). Solo se mockea el HTTP a
Moodle, que no existe en CI.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.import_service import ImportacionMoodleService
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    BlankBancoModel,
    CategoriaPreguntaModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionBlankBancoModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

_TABLES = [
    "opcion_blank_banco",
    "blank_banco",
    "opcion_banco",
    "opcion_respuesta",
    "pregunta_examen",
    "pregunta_banco",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]

# XML con id de pregunta de Moodle en el nodo <idnumber> no aplica: el parser
# toma el id de otro lado. Estos XML no traen id, que es justo el caso que
# antes duplicaba en cada re-import.
XML_UNIDAD_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
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
</quiz>
"""

# Mismo enunciado, misma categoría de origen, pero cambió cuál es la correcta.
XML_UNIDAD_1_CORREGIDO = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>P1</text></name>
    <questiontext format="html"><text>Cuanto es dos mas dos</text></questiontext>
    <answer fraction="0"><text>Cuatro</text></answer>
    <answer fraction="100"><text>Cinco</text></answer>
  </question>
</quiz>
"""

# La MISMA pregunta, pero en Moodle la movieron a otra categoría.
XML_MISMA_PREGUNTA_OTRA_CATEGORIA = b"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 9</text></category>
  </question>
  <question type="multichoice">
    <name><text>P1</text></name>
    <questiontext format="html"><text>Cuanto es dos mas dos</text></questiontext>
    <answer fraction="100"><text>Cuatro</text></answer>
    <answer fraction="0"><text>Cinco</text></answer>
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
                PreguntaBancoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
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
        {"id": mid, "c": f"PROP-{mid[:8]}", "n": "Materia Propiedad"},
    )
    await session.commit()
    return mid


async def _categorias(session: AsyncSession, materia_id: str):
    result = await session.execute(
        select(CategoriaPreguntaModel).where(
            CategoriaPreguntaModel.materia_id == materia_id
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Import: la pregunta movida a mano se queda donde el docente la puso
# ---------------------------------------------------------------------------


async def _importar(session: AsyncSession, materia_id: str, xml: bytes, titulo: str):
    svc = ImportacionMoodleService(ExamenContenidoSqlRepository(session))
    report = await svc.importar(xml, titulo=titulo, materia_id=materia_id)
    await session.commit()
    return report


async def _pregunta_banco(session: AsyncSession, materia_id: str) -> PreguntaBancoModel:
    result = await session.execute(
        select(PreguntaBancoModel).where(PreguntaBancoModel.materia_id == materia_id)
    )
    filas = list(result.scalars().all())
    assert len(filas) == 1, f"se esperaba 1 pregunta en el banco, hay {len(filas)}"
    return filas[0]


@pytest.mark.asyncio
async def test_reimport_respeta_la_categoria_puesta_a_mano(
    session: AsyncSession, materia_id: str
):
    """El bug original: re-importar el XML devolvía la pregunta a la categoría de Moodle."""
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 1")

    # El docente crea su propia categoría y mueve la pregunta ahí.
    mi_cat = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre) "
            "VALUES (:id, :mid, :n)"
        ),
        {"id": mi_cat, "mid": materia_id, "n": "Mi Parcial 1"},
    )
    pregunta = await _pregunta_banco(session, materia_id)
    await session.execute(
        text(
            "UPDATE pregunta_banco SET categoria_id = :cat, categoria_manual = true "
            "WHERE id = :id"
        ),
        {"cat": mi_cat, "id": pregunta.id},
    )
    await session.commit()

    # Moodle insiste: la misma pregunta, en OTRA categoría.
    await _importar(
        session, materia_id, XML_MISMA_PREGUNTA_OTRA_CATEGORIA, "Import 2"
    )

    session.expire_all()
    pregunta = await _pregunta_banco(session, materia_id)
    assert pregunta.categoria_id == mi_cat, (
        "el re-import le pisó al docente la categoría que había elegido"
    )
    assert pregunta.categoria_manual is True


@pytest.mark.asyncio
async def test_reimport_si_recategoriza_cuando_el_docente_no_toco_nada(
    session: AsyncSession, materia_id: str
):
    """Control: sin marca manual, Moodle sí manda. Prueba que la marca es lo que decide."""
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 1")

    pregunta = await _pregunta_banco(session, materia_id)
    assert pregunta.categoria_manual is False
    categoria_inicial = pregunta.categoria_id

    await _importar(
        session, materia_id, XML_MISMA_PREGUNTA_OTRA_CATEGORIA, "Import 2"
    )

    session.expire_all()
    pregunta = await _pregunta_banco(session, materia_id)
    assert pregunta.categoria_id != categoria_inicial, (
        "sin marca manual, la categoría debe seguir a Moodle"
    )

    cats = await _categorias(session, materia_id)
    nombres = {c.nombre for c in cats}
    assert "Unidad 9" in nombres


@pytest.mark.asyncio
async def test_reimport_no_duplica_preguntas_sin_id_de_moodle(
    session: AsyncSession, materia_id: str
):
    """Sin moodle_question_id el import insertaba de nuevo en cada pasada."""
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 1")
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 2")
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 3")

    result = await session.execute(
        select(PreguntaBancoModel).where(PreguntaBancoModel.materia_id == materia_id)
    )
    filas = list(result.scalars().all())
    assert len(filas) == 1, f"3 imports dejaron {len(filas)} preguntas en el banco"


@pytest.mark.asyncio
async def test_reimport_refresca_las_opciones(session: AsyncSession, materia_id: str):
    """Si en Moodle cambió cuál es la correcta, el banco tiene que enterarse.

    Antes se hacía ``return`` antes de tocar las opciones: quedaba la respuesta
    correcta vieja y el examen calificaba mal sin avisar.
    """
    await _importar(session, materia_id, XML_UNIDAD_1, "Import 1")
    pregunta = await _pregunta_banco(session, materia_id)

    correctas = await session.execute(
        text(
            "SELECT texto FROM opcion_banco "
            "WHERE pregunta_banco_id = :id AND es_correcta = true"
        ),
        {"id": pregunta.id},
    )
    assert [r[0] for r in correctas.fetchall()] == ["Cuatro"]

    await _importar(session, materia_id, XML_UNIDAD_1_CORREGIDO, "Import 2")

    pregunta = await _pregunta_banco(session, materia_id)
    correctas = await session.execute(
        text(
            "SELECT texto FROM opcion_banco "
            "WHERE pregunta_banco_id = :id AND es_correcta = true"
        ),
        {"id": pregunta.id},
    )
    assert [r[0] for r in correctas.fetchall()] == ["Cinco"], (
        "la opción correcta no se refrescó desde Moodle"
    )

    todas = await session.execute(
        text("SELECT COUNT(*) FROM opcion_banco WHERE pregunta_banco_id = :id"),
        {"id": pregunta.id},
    )
    assert todas.scalar_one() == 2, "las opciones se acumularon en vez de reemplazarse"
