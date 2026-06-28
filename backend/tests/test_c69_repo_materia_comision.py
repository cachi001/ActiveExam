"""6.3 RED → 6.4 GREEN: tests de repositorio materia/comisión contra DB real (C-69, D11).

Requieren DATABASE_URL seteada. Sin ella, se saltan.

Cubre:
- Persistir y recuperar materia/comisión.
- Unicidad de codigo de materia → rechaza duplicado.
- Unicidad (materia_id, codigo) de comisión → rechaza duplicado; mismo codigo en
  OTRA materia sí se permite.
- Un examen con comision_id asignado deriva transitivamente su materia.
- Un examen con comision_id NULL sigue siendo válido y recuperable.
- FK examen→comisión ON DELETE SET NULL (semántica de la migración 0028).
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import (
    Comision,
    ExamenContenido,
    Materia,
    OpcionRespuesta,
    Pregunta,
)
from app.domain.exam_content.errors import (
    ComisionDuplicadaError,
    MateriaDuplicadaError,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401 - registra tablas
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

# Orden de drop (hijas primero) y de create (padres primero) por las FKs.
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
        # Padres primero: materia, comision, luego examen_contenido y sus hijas.
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
        # La FK examen→comisión ON DELETE SET NULL vive en la migración 0028,
        # no en el ORM (para no romper los create_all de otros tests). La
        # reproducimos aquí para verificar su semántica real (SET NULL).
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


# ---------------------------------------------------------------------------
# Materia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardar_y_recuperar_materia(session):
    repo = MateriaSqlRepository(session)
    guardada = await repo.guardar(Materia(codigo="ALG-101", nombre="Álgebra I"))
    assert guardada.id is not None

    recuperada = await repo.obtener(guardada.id)
    assert recuperada is not None
    assert recuperada.codigo == "ALG-101"
    assert recuperada.nombre == "Álgebra I"


@pytest.mark.asyncio
async def test_materia_codigo_unico_rechaza_duplicado(session):
    repo = MateriaSqlRepository(session)
    await repo.guardar(Materia(codigo="DUP-1", nombre="Una"))
    with pytest.raises(MateriaDuplicadaError):
        await repo.guardar(Materia(codigo="DUP-1", nombre="Otra"))


@pytest.mark.asyncio
async def test_obtener_materia_inexistente_devuelve_none(session):
    repo = MateriaSqlRepository(session)
    assert await repo.obtener("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# Comisión
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardar_y_recuperar_comision(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    materia = await materia_repo.guardar(Materia(codigo="FIS-201", nombre="Física"))

    guardada = await comision_repo.guardar(
        Comision(
            codigo="C-A",
            nombre="Comisión A",
            materia_id=materia.id,
            periodo="1C",
            anio=2026,
        )
    )
    assert guardada.id is not None

    recuperada = await comision_repo.obtener(guardada.id)
    assert recuperada is not None
    assert recuperada.codigo == "C-A"
    assert recuperada.materia_id == materia.id
    assert recuperada.periodo == "1C"
    assert recuperada.anio == 2026


@pytest.mark.asyncio
async def test_comision_unique_materia_codigo_rechaza_duplicado(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    materia = await materia_repo.guardar(Materia(codigo="QUI-301", nombre="Química"))

    await comision_repo.guardar(
        Comision(codigo="C-1", nombre="Comisión 1", materia_id=materia.id)
    )
    with pytest.raises(ComisionDuplicadaError):
        await comision_repo.guardar(
            Comision(codigo="C-1", nombre="Comisión 1 bis", materia_id=materia.id)
        )


@pytest.mark.asyncio
async def test_comision_mismo_codigo_otra_materia_se_permite(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    m1 = await materia_repo.guardar(Materia(codigo="MAT-A", nombre="Mat A"))
    m2 = await materia_repo.guardar(Materia(codigo="MAT-B", nombre="Mat B"))

    c1 = await comision_repo.guardar(
        Comision(codigo="C-X", nombre="CX en A", materia_id=m1.id)
    )
    c2 = await comision_repo.guardar(
        Comision(codigo="C-X", nombre="CX en B", materia_id=m2.id)
    )
    assert c1.id != c2.id


# ---------------------------------------------------------------------------
# Examen ↔ comisión (D11): NULLABLE + transitividad de materia
# ---------------------------------------------------------------------------


def _examen(comision_id: str | None) -> ExamenContenido:
    return ExamenContenido(
        titulo="Parcial",
        comision_id=comision_id,
        preguntas=(
            Pregunta(
                enunciado="¿2+2?",
                tipo="multichoice",
                opciones=(
                    OpcionRespuesta(texto="4", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="5", es_correcta=False, orden=1),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_examen_sin_comision_es_valido_y_recuperable(session):
    """D11: comision_id NULL es estado válido y recuperable."""
    examen_repo = ExamenContenidoSqlRepository(session)
    guardado = await examen_repo.guardar(_examen(comision_id=None))
    recuperado = await examen_repo.obtener(guardado.id)
    assert recuperado is not None
    assert recuperado.comision_id is None
    assert len(recuperado.preguntas) == 1


@pytest.mark.asyncio
async def test_examen_con_comision_deriva_materia_transitivamente(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="TR-1", nombre="Transitiva"))
    comision = await comision_repo.guardar(
        Comision(codigo="C-T", nombre="Com T", materia_id=materia.id)
    )
    examen = await examen_repo.guardar(_examen(comision_id=comision.id))

    # Transitividad: examen.comision_id → comision.materia_id → materia.
    recuperado = await examen_repo.obtener(examen.id)
    assert recuperado is not None
    assert recuperado.comision_id == comision.id

    com = await comision_repo.obtener(recuperado.comision_id)
    assert com is not None
    materia_derivada = await materia_repo.obtener(com.materia_id)
    assert materia_derivada is not None
    assert materia_derivada.id == materia.id
    assert materia_derivada.codigo == "TR-1"


@pytest.mark.asyncio
async def test_fk_examen_comision_set_null_al_borrar_comision(session):
    """Borrar una comisión NO borra el examen: su comision_id pasa a NULL (SET NULL)."""
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="SN-1", nombre="SetNull"))
    comision = await comision_repo.guardar(
        Comision(codigo="C-SN", nombre="Com SN", materia_id=materia.id)
    )
    examen = await examen_repo.guardar(_examen(comision_id=comision.id))
    await session.commit()

    await session.execute(
        text("DELETE FROM comision WHERE id = :cid"), {"cid": comision.id}
    )
    await session.commit()
    # El DELETE aplicó SET NULL en la DB; vaciamos el identity-map para re-leer
    # desde la DB y no obtener la instancia cacheada con el comision_id viejo.
    session.expire_all()

    recuperado = await examen_repo.obtener(examen.id)
    assert recuperado is not None  # el examen sobrevive
    assert recuperado.comision_id is None  # FK puesta a NULL
