"""Editar una pregunta en Moodle y volver a subir el banco NO puede duplicarla.

El import por XML resolvía "nueva vs actualizada" comparando el ENUNCIADO, porque
`moodle_question_id` solo se llena por el sync vía API y un export XML no lo trae.
Consecuencia: corregir una coma en una pregunta y re-subir el archivo la daba de
alta como pregunta NUEVA, y la versión vieja quedaba viva en el banco. Las dos
podían salir sorteadas en el mismo examen, y no hay forma de borrar una pregunta
desde la aplicación.

El export de Moodle sí trae algo estable: `<name><text>`, el nombre de la pregunta.
Con eso alcanza para reconocerla aunque le cambien el texto.

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

from app.application.exam_content.import_service import importar_banco_desde_xml
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


def _xml(enunciado_p1: str) -> bytes:
    """Mismo banco, con el enunciado de P1 variable. El `name` NO cambia."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="category">
    <category><text>$course$/top/Unidad 1</text></category>
  </question>
  <question type="multichoice">
    <name><text>CC-P01 (guarda y retorno)</text></name>
    <questiontext format="html"><text>{enunciado_p1}</text></questiontext>
    <answer fraction="100"><text>Cuatro</text></answer>
    <answer fraction="0"><text>Cinco</text></answer>
  </question>
  <question type="multichoice">
    <name><text>CC-P02 (otra)</text></name>
    <questiontext format="html"><text>Cuanto es tres mas tres</text></questiontext>
    <answer fraction="100"><text>Seis</text></answer>
    <answer fraction="0"><text>Siete</text></answer>
  </question>
</quiz>
""".encode()


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
        {"id": mid, "c": f"REIMP-{mid[:8]}", "n": "Materia Reimport"},
    )
    await session.commit()
    return mid


async def _cuantas(session: AsyncSession, materia_id: str) -> int:
    res = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_banco WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    return res.scalar_one()


@pytest.mark.asyncio
async def test_editar_el_enunciado_actualiza_la_pregunta_y_no_crea_otra(
    session: AsyncSession, materia_id: str
):
    """El caso que rompía: mismo `name`, enunciado corregido."""
    await importar_banco_desde_xml(session, _xml("Cuanto es dos mas dos"), materia_id)
    await session.commit()
    assert await _cuantas(session, materia_id) == 2

    report = await importar_banco_desde_xml(
        session, _xml("Cuanto es dos mas dos (corregido)"), materia_id
    )
    await session.commit()

    assert await _cuantas(session, materia_id) == 2, "se duplicó la pregunta editada"
    assert report.preguntas_nuevas == 0
    assert report.preguntas_actualizadas == 2

    enunciados = await session.execute(
        text("SELECT enunciado FROM pregunta_banco WHERE materia_id = :mid ORDER BY 1"),
        {"mid": materia_id},
    )
    textos = [r[0] for r in enunciados]
    assert any("corregido" in t for t in textos), "no quedó el texto nuevo"
    assert not any(t == "Cuanto es dos mas dos" for t in textos), "quedó el texto viejo"


@pytest.mark.asyncio
async def test_reimportar_identico_sigue_sin_duplicar(
    session: AsyncSession, materia_id: str
):
    """Triangulación: el caso que ya andaba no se rompe."""
    await importar_banco_desde_xml(session, _xml("Cuanto es dos mas dos"), materia_id)
    await session.commit()
    report = await importar_banco_desde_xml(
        session, _xml("Cuanto es dos mas dos"), materia_id
    )
    await session.commit()

    assert await _cuantas(session, materia_id) == 2
    assert report.preguntas_nuevas == 0


@pytest.mark.asyncio
async def test_una_pregunta_con_nombre_distinto_si_es_nueva(
    session: AsyncSession, materia_id: str
):
    """Triangulación al revés: otro `name` es otra pregunta, aunque se parezca."""
    await importar_banco_desde_xml(session, _xml("Cuanto es dos mas dos"), materia_id)
    await session.commit()

    xml_con_una_mas = _xml("Cuanto es dos mas dos").replace(
        b"</quiz>",
        b"""  <question type="multichoice">
    <name><text>CC-P03 (agregada)</text></name>
    <questiontext format="html"><text>Cuanto es cuatro mas cuatro</text></questiontext>
    <answer fraction="100"><text>Ocho</text></answer>
    <answer fraction="0"><text>Nueve</text></answer>
  </question>
</quiz>""",
    )
    report = await importar_banco_desde_xml(session, xml_con_una_mas, materia_id)
    await session.commit()

    assert await _cuantas(session, materia_id) == 3
    assert report.preguntas_nuevas == 1
    assert report.preguntas_actualizadas == 2


@pytest.mark.asyncio
async def test_banco_viejo_sin_nombre_guardado_se_reconoce_por_enunciado(
    session: AsyncSession, materia_id: str
):
    """Compatibilidad: las preguntas que ya estaban en la base no tienen nombre
    guardado. Ahí el enunciado sigue siendo la única forma de reconocerlas, y no
    puede empezar a duplicarlas."""
    await importar_banco_desde_xml(session, _xml("Cuanto es dos mas dos"), materia_id)
    await session.commit()
    # Simula el estado previo a la migración: sin nombre_moodle.
    await session.execute(
        text("UPDATE pregunta_banco SET nombre_moodle = NULL WHERE materia_id = :mid"),
        {"mid": materia_id},
    )
    await session.commit()

    report = await importar_banco_desde_xml(
        session, _xml("Cuanto es dos mas dos"), materia_id
    )
    await session.commit()

    assert await _cuantas(session, materia_id) == 2
    assert report.preguntas_nuevas == 0
