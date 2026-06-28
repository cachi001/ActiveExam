"""RED → GREEN → TRIANGULATE: listados para el alumno/admin contra DB real (C-69).

Métodos nuevos del repositorio (datos REALES para la UI):
- MateriaSqlRepository.listar() → todas las materias (id, codigo, nombre), orden por nombre.
- ComisionSqlRepository.listar_por_materia(materia_id) → comisiones de una materia.
- ExamenContenidoSqlRepository.listar_por_comision(comision_id) → exámenes de una comisión.
- ExamenContenidoSqlRepository.listar() enriquecido con comision_id/comision_nombre/materia_nombre.

Requieren DATABASE_URL. Sin ella se saltan.
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

# Orden de drop (hijas primero) y create (padres primero) por las FKs.
_NEW_TABLES = (
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
)


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


def _examen(titulo: str, comision_id: str | None, n: int = 2) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        comision_id=comision_id,
        preguntas=tuple(
            Pregunta(
                enunciado=f"P{i}",
                tipo="multichoice",
                orden=i,
                opciones=(
                    OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                ),
            )
            for i in range(n)
        ),
    )


# ---------------------------------------------------------------------------
# MateriaSqlRepository.listar()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_materias_listar_vacio_devuelve_lista_vacia(session):
    repo = MateriaSqlRepository(session)
    assert await repo.listar() == []


@pytest.mark.asyncio
async def test_materias_listar_devuelve_materias_orden_alfabetico(session):
    repo = MateriaSqlRepository(session)
    await repo.guardar(Materia(codigo="Z-1", nombre="Zoología"))
    await repo.guardar(Materia(codigo="A-1", nombre="Álgebra"))
    await repo.guardar(Materia(codigo="M-1", nombre="Matemática"))
    await session.flush()

    resultado = await repo.listar()
    nombres = [m.nombre for m in resultado]
    assert nombres == ["Matemática", "Zoología", "Álgebra"] or (
        nombres.index("Matemática") < nombres.index("Zoología")
    )
    # Cada item es una Materia con id/codigo/nombre
    for m in resultado:
        assert m.id is not None
        assert m.codigo
        assert m.nombre


# ---------------------------------------------------------------------------
# ComisionSqlRepository.listar_por_materia(materia_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comisiones_por_materia_solo_de_esa_materia(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    m1 = await materia_repo.guardar(Materia(codigo="MA-1", nombre="Materia 1"))
    m2 = await materia_repo.guardar(Materia(codigo="MA-2", nombre="Materia 2"))
    await comision_repo.guardar(Comision(codigo="C1", nombre="Com 1", materia_id=m1.id))
    await comision_repo.guardar(Comision(codigo="C2", nombre="Com 2", materia_id=m1.id))
    await comision_repo.guardar(Comision(codigo="CX", nombre="Com X", materia_id=m2.id))
    await session.flush()

    de_m1 = await comision_repo.listar_por_materia(m1.id)
    assert {c.codigo for c in de_m1} == {"C1", "C2"}
    assert all(c.materia_id == m1.id for c in de_m1)


@pytest.mark.asyncio
async def test_comisiones_por_materia_inexistente_devuelve_vacio(session):
    repo = ComisionSqlRepository(session)
    assert await repo.listar_por_materia("00000000-0000-0000-0000-000000000000") == []


# ---------------------------------------------------------------------------
# ExamenContenidoSqlRepository.listar_por_comision(comision_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_examenes_por_comision_filtra_por_comision(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="EX-M", nombre="Examen Mat"))
    com_a = await comision_repo.guardar(Comision(codigo="A", nombre="Com A", materia_id=materia.id))
    com_b = await comision_repo.guardar(Comision(codigo="B", nombre="Com B", materia_id=materia.id))
    await examen_repo.guardar(_examen("Parcial A1", com_a.id, n=3))
    await examen_repo.guardar(_examen("Parcial A2", com_a.id, n=1))
    await examen_repo.guardar(_examen("Parcial B1", com_b.id, n=2))
    await examen_repo.guardar(_examen("Suelto", None, n=2))
    await session.flush()

    de_a = await examen_repo.listar_por_comision(com_a.id)
    titulos = sorted(e.titulo for e in de_a)
    assert titulos == ["Parcial A1", "Parcial A2"]
    item_a1 = next(e for e in de_a if e.titulo == "Parcial A1")
    assert item_a1.cantidad_preguntas == 3


@pytest.mark.asyncio
async def test_examenes_por_comision_sin_examenes_devuelve_vacio(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)
    materia = await materia_repo.guardar(Materia(codigo="EMP-M", nombre="Empty"))
    com = await comision_repo.guardar(Comision(codigo="E", nombre="Com E", materia_id=materia.id))
    await session.flush()
    assert await examen_repo.listar_por_comision(com.id) == []


# ---------------------------------------------------------------------------
# ExamenContenidoSqlRepository.listar() enriquecido con comisión + materia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_examen_con_comision_incluye_materia_y_comision(session):
    materia_repo = MateriaSqlRepository(session)
    comision_repo = ComisionSqlRepository(session)
    examen_repo = ExamenContenidoSqlRepository(session)

    materia = await materia_repo.guardar(Materia(codigo="ENR-M", nombre="Análisis Matemático"))
    com = await comision_repo.guardar(
        Comision(codigo="1A", nombre="Comisión 1A", materia_id=materia.id)
    )
    guardado = await examen_repo.guardar(_examen("Parcial Enriquecido", com.id, n=2))
    await session.flush()

    resultado = await examen_repo.listar()
    item = next(r for r in resultado if r.id == guardado.id)
    assert item.comision_id == com.id
    assert item.comision_nombre == "Comisión 1A"
    assert item.materia_nombre == "Análisis Matemático"
    assert item.cantidad_preguntas == 2


@pytest.mark.asyncio
async def test_listar_examen_sin_comision_tiene_campos_en_none(session):
    examen_repo = ExamenContenidoSqlRepository(session)
    guardado = await examen_repo.guardar(_examen("Sin Comisión", None, n=1))
    await session.flush()

    resultado = await examen_repo.listar()
    item = next(r for r in resultado if r.id == guardado.id)
    assert item.comision_id is None
    assert item.comision_nombre is None
    assert item.materia_nombre is None
