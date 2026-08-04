"""C-74 SS5 RED -> GREEN -> TRIANGULATE: import XML Moodle con preguntas cloze.

Cubre:
  5.2 Parser cloze: BlankData + OpcionClozeDato correctamente extraidos.
  5.6 GREEN: importar XML real con cloze -> se persisten blanks y opciones en DB;
      ninguna pregunta cae a "tipo no soportado".
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.moodle_parser import parse_cloze_blanks, parse_moodle_xml
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    MateriaModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "moodle"

_TABLES = [
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "materia",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
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


@pytest_asyncio.fixture
async def materia_id(session: AsyncSession) -> str:
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"CL-{mid[:8]}", "n": "Materia Cloze Test"},
    )
    await session.commit()
    return mid


# ---------------------------------------------------------------------------
# Tests puros (sin DB) -- parser
# ---------------------------------------------------------------------------


def test_5_2a_parse_cloze_blanks_multichoice():
    """5.2 RED->GREEN: extrae blank MULTICHOICE con opciones correctas."""
    texto = "El resultado es {1:MULTICHOICE:=Verdadero~Falso} siempre."
    blanks = parse_cloze_blanks(texto)
    assert len(blanks) == 1
    b = blanks[0]
    assert b.tipo == "multichoice"
    assert b.texto_antes == "El resultado es "
    assert b.texto_despues == " siempre."
    assert len(b.opciones) == 2
    assert b.opciones[0].texto == "Verdadero"
    assert b.opciones[0].es_correcta is True
    assert b.opciones[1].texto == "Falso"
    assert b.opciones[1].es_correcta is False


def test_5_2b_parse_cloze_blanks_dos_blanks():
    """5.2 TRIANGULATE: dos blanks en el mismo texto."""
    texto = "A es {1:MULTICHOICE:=X~Y} y B es {2:SHORTANSWER:=Z}."
    blanks = parse_cloze_blanks(texto)
    assert len(blanks) == 2
    assert blanks[0].tipo == "multichoice"
    assert blanks[0].texto_antes == "A es "
    assert blanks[0].texto_despues == " y B es "
    assert blanks[1].tipo == "shortanswer"
    assert blanks[1].texto_antes == " y B es "
    assert blanks[1].texto_despues == "."


def test_5_2c_parse_cloze_peso_explicito():
    """5.2 TRIANGULATE: opcion con prefijo %100% es correcta, %0% es incorrecta."""
    texto = "Elige: {1:MULTICHOICE:%100%correcto~%0%incorrecto}"
    blanks = parse_cloze_blanks(texto)
    assert len(blanks) == 1
    assert blanks[0].opciones[0].es_correcta is True
    assert blanks[0].opciones[0].peso == 100
    assert blanks[0].opciones[1].es_correcta is False
    assert blanks[0].opciones[1].peso == 0


def test_5_3_tipos_soportados_incluye_cloze():
    """5.3: el parser acepta cloze y multianswer como tipos soportados."""
    xml = b"""<?xml version="1.0"?>
<quiz>
  <question type="cloze">
    <name><text>Cloze Q</text></name>
    <questiontext format="html">
      <text>Completa: {1:MULTICHOICE:=A~B}</text>
    </questiontext>
  </question>
</quiz>"""
    result = parse_moodle_xml(xml)
    assert len(result.preguntas) == 1
    assert result.preguntas[0].tipo == "cloze"
    assert len(result.omitidas) == 0


def test_5_4_strip_html_preserva_placeholders():
    """5.4: _strip_html no destruye {N:TYPE:...} embebidos."""
    from app.application.exam_content.moodle_parser import _strip_html
    texto = "<p>Evaluar <code>5</code> {1:MULTICHOICE:=True~False} retorna</p>"
    resultado = _strip_html(texto)
    assert "{1:MULTICHOICE:=True~False}" in resultado
    assert "<p>" not in resultado
    assert "<code>" not in resultado


# ---------------------------------------------------------------------------
# Test de integracion con DB (5.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_5_6_import_cloze_persiste_blanks_y_opciones(session: AsyncSession, materia_id: str):
    """5.6 GREEN: importar XML cloze real -> blanks y opciones persisten en DB."""
    from app.application.exam_content.import_service import ImportacionMoodleService
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    xml_bytes = (FIXTURE_DIR / "moodle_cloze_real.xml").read_bytes()

    repo = ExamenContenidoSqlRepository(session)
    svc = ImportacionMoodleService(repo)
    report = await svc.importar(xml_bytes, titulo="Test cloze")
    await session.commit()

    # 3 cloze + 1 multichoice = 4 preguntas, ninguna omitida
    assert report.importadas == 4
    assert report.omitidas == []

    # Verificar que los blanks se persistieron
    blanks_result = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_cloze_blank")
    )
    total_blanks = blanks_result.scalar()
    assert total_blanks >= 6, f"Esperaba >= 6 blanks cloze, tiene {total_blanks}"

    # Cada blank debe tener al menos 1 opcion
    opciones_result = await session.execute(
        text("SELECT COUNT(*) FROM opcion_cloze_blank")
    )
    total_opciones = opciones_result.scalar()
    assert total_opciones >= total_blanks, "Debe haber al menos 1 opcion por blank"

    # Cada blank debe tener al menos 1 opcion correcta
    # (SHORTANSWER puede tener varias correctas: =len~=length -> 2 correctas)
    blanks_sin_correcta_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT blank_id
                FROM opcion_cloze_blank
                WHERE es_correcta = true
                GROUP BY blank_id
                HAVING COUNT(*) < 1
            ) AS mal
        """)
    )
    blanks_sin_correcta = blanks_sin_correcta_result.scalar()
    assert blanks_sin_correcta == 0, f"{blanks_sin_correcta} blanks sin ninguna opcion correcta"


@pytest.mark.asyncio
async def test_5_6b_pregunta_multichoice_no_tiene_blanks(session: AsyncSession):
    """5.6 TRIANGULATE: una pregunta multichoice normal no genera blanks cloze."""
    from app.application.exam_content.import_service import ImportacionMoodleService
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    xml_mc = b"""<?xml version="1.0"?>
<quiz>
  <question type="multichoice">
    <name><text>Q MC</text></name>
    <questiontext format="html"><text>Texto normal sin blanks</text></questiontext>
    <answer fraction="100"><text>Correcta</text></answer>
    <answer fraction="0"><text>Incorrecta</text></answer>
  </question>
</quiz>"""

    repo = ExamenContenidoSqlRepository(session)
    svc = ImportacionMoodleService(repo)
    report = await svc.importar(xml_mc, titulo="Test MC sin blanks")
    await session.commit()

    assert report.importadas == 1

    # Verificar 0 blanks para esta pregunta
    blanks_result = await session.execute(
        text("""
            SELECT COUNT(*)
            FROM pregunta_cloze_blank pcb
            JOIN pregunta_examen pe ON pe.id = pcb.pregunta_id
            JOIN examen_contenido ec ON ec.id = pe.examen_id
            WHERE ec.titulo = 'Test MC sin blanks'
        """)
    )
    assert blanks_result.scalar() == 0