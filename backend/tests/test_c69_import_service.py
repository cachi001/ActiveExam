"""2.3 RED → 2.4 GREEN: tests del servicio de importación contra DB real.

Requieren DATABASE_URL. Sin ella, se saltan.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.errors import MoodleXmlInvalidoError, MoodleXmlVacioError
from app.application.exam_content.import_service import ImportacionMoodleService
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

FIXTURES = Path(__file__).parent / "fixtures" / "moodle"
_NEW_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido")


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


# ---------------------------------------------------------------------------
# 2.3 RED — tests del servicio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_importar_xml_crea_examen(session):
    """Un XML válido crea un examen en la DB y devuelve reporte."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    report = await service.importar(xml, titulo="Test Álgebra")

    assert report.examen_id is not None
    assert report.importadas == 2
    assert len(report.omitidas) == 0


@pytest.mark.asyncio
async def test_importar_sin_comision_es_valido(session):
    """D11: el examen creado tiene comision_id=None y es recuperable."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    report = await service.importar(xml)

    examen = await repo.obtener(report.examen_id)
    assert examen is not None
    assert examen.comision_id is None


@pytest.mark.asyncio
async def test_importar_usa_titulo_default(session):
    """Sin título explícito usa 'Examen importado'."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    report = await service.importar(xml)

    examen = await repo.obtener(report.examen_id)
    assert examen is not None
    assert examen.titulo == "Examen importado"


@pytest.mark.asyncio
async def test_importar_xml_mixto_reporta_omitidas(session):
    """XML con tipos soportados + no soportados: importa los soportados, reporta omitidas."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "mixed_unsupported.xml").read_bytes()
    report = await service.importar(xml)

    # C-74 agregó soporte de cloze: se importa multichoice + cloze, omite essay.
    assert report.importadas == 2
    assert len(report.omitidas) == 1
    assert report.omitidas[0].tipo == "essay"


@pytest.mark.asyncio
async def test_importar_con_moodle_target_lo_persiste(session):
    """D12: importar con moodle_courseid/cmid los guarda en el examen."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    report = await service.importar(xml, moodle_courseid=321, moodle_cmid=9)

    examen = await repo.obtener(report.examen_id)
    assert examen is not None
    assert examen.moodle_courseid == 321
    assert examen.moodle_cmid == 9


@pytest.mark.asyncio
async def test_importar_sin_moodle_target_queda_none(session):
    """D12: sin destino explícito, courseid/cmid quedan None (fallback global)."""
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    report = await service.importar(xml)

    examen = await repo.obtener(report.examen_id)
    assert examen is not None
    assert examen.moodle_courseid is None
    assert examen.moodle_cmid is None


@pytest.mark.asyncio
async def test_importar_xml_invalido_lanza_error(session):
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    with pytest.raises(MoodleXmlInvalidoError):
        await service.importar(b"not xml <<<")


@pytest.mark.asyncio
async def test_importar_xml_vacio_lanza_error(session):
    repo = ExamenContenidoSqlRepository(session)
    service = ImportacionMoodleService(repo)

    xml = (FIXTURES / "invalid_empty.xml").read_bytes()
    with pytest.raises(MoodleXmlVacioError):
        await service.importar(xml)
