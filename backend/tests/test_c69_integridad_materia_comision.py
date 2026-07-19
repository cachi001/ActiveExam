"""6.8 TRIANGULATE: invariantes de integridad materia/comisión (C-69, D11).

Triangula sobre lo ya cubierto en dominio/repo/endpoint con ángulos nuevos:
- Una comisión NO puede referenciar una materia inexistente (FK comision→materia).
- Re-asociar un examen a otra comisión lo deja con EXACTAMENTE una (la última).
- Un examen sin comisión es un estado válido (puede desasociarse a NULL).

Requiere DATABASE_URL.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import (
    Comision,
    ExamenContenido,
    Materia,
    OpcionRespuesta,
    Pregunta,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
    ExamenContenidoSqlRepository,
    MateriaSqlRepository,
)
from app.application.exam_content.codigo_matriculacion import componer_codigo
import itertools

# `codigo_matriculacion` NOT NULL (0038): en producción lo autogenera el servicio;
# estos tests van al repo directo, así que lo resuelven acá (único/determinístico).
_cm_seq = itertools.count(1)


def _cm(materia_codigo: str) -> str:
    return componer_codigo(materia_codigo, f"T{next(_cm_seq):03d}")


_NEW_TABLES = (
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
)
_FK_EXAMEN_COMISION = "fk_examen_contenido_comision"


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
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
        await conn.execute(
            text(
                f'ALTER TABLE examen_contenido ADD CONSTRAINT "{_FK_EXAMEN_COMISION}" '
                "FOREIGN KEY (comision_id) REFERENCES comision(id) ON DELETE SET NULL"
            )
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


def _examen(comision_id=None) -> ExamenContenido:
    return ExamenContenido(
        titulo="Parcial",
        comision_id=comision_id,
        preguntas=(
            Pregunta(
                enunciado="¿Q?",
                tipo="truefalse",
                opciones=(
                    OpcionRespuesta(texto="V", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="F", es_correcta=False, orden=1),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_comision_con_materia_inexistente_es_rechazada_por_fk(session):
    """La FK comision→materia rechaza una comisión que apunta a una materia inexistente."""
    comision_repo = ComisionSqlRepository(session)
    with pytest.raises(IntegrityError):
        await comision_repo.guardar(
            Comision(
                codigo="C-ORPH",
                nombre="Huérfana",
                materia_id="00000000-0000-0000-0000-000000000000",
                codigo_matriculacion=_cm("ORPH"),
            )
        )


@pytest.mark.asyncio
async def test_reasociar_examen_deja_exactamente_una_comision(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="RE-1", nombre="Reasoc"))
    c1 = await comision_repo.guardar(
        Comision(codigo="C-1", nombre="Uno", materia_id=materia.id, codigo_matriculacion=_cm(materia.codigo))
    )
    c2 = await comision_repo.guardar(
        Comision(codigo="C-2", nombre="Dos", materia_id=materia.id, codigo_matriculacion=_cm(materia.codigo))
    )
    examen = await examen_repo.guardar(_examen(comision_id=c1.id))

    await examen_repo.asociar_comision(examen.id, c2.id)
    recuperado = await examen_repo.obtener(examen.id)
    assert recuperado is not None
    assert recuperado.comision_id == c2.id  # exactamente una: la última


@pytest.mark.asyncio
async def test_examen_se_puede_desasociar_a_null(session):
    """Desasociar (comision_id=None) vuelve al estado válido sin comisión (D11)."""
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="DS-1", nombre="Desasoc"))
    comision = await comision_repo.guardar(
        Comision(codigo="C-D", nombre="ComD", materia_id=materia.id, codigo_matriculacion=_cm(materia.codigo))
    )
    examen = await examen_repo.guardar(_examen(comision_id=comision.id))

    await examen_repo.asociar_comision(examen.id, None)
    recuperado = await examen_repo.obtener(examen.id)
    assert recuperado is not None
    assert recuperado.comision_id is None
