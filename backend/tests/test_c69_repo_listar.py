"""RED → GREEN → TRIANGULATE: tests del método listar() del repositorio de ExamenContenido.

TDD Cycle:
  RED:         tests escritos primero — referencian listar() que aún no existe.
  GREEN:       se agrega listar() al ExamenContenidoSqlRepository.
  TRIANGULATE: múltiples escenarios (vacío, uno, varios, orden alfabético).

Requieren DATABASE_URL. Sin ella se saltan.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)

# listar() hace LEFT JOIN a comision/materia (D11): esas tablas deben existir.
_NEW_TABLES = (
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
)


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


def _examen_con_n_preguntas(titulo: str, n: int) -> ExamenContenido:
    """Crea un examen de prueba con n preguntas multichoice."""
    preguntas = tuple(
        Pregunta(
            enunciado=f"Pregunta {i + 1}",
            tipo="multichoice",
            orden=i,
            opciones=(
                OpcionRespuesta(texto="Opción A", es_correcta=True, orden=0),
                OpcionRespuesta(texto="Opción B", es_correcta=False, orden=1),
            ),
        )
        for i in range(n)
    )
    return ExamenContenido(titulo=titulo, preguntas=preguntas, comision_id=None)


# ---------------------------------------------------------------------------
# RED: test del caso vacío (listar() no existe aún — falla en RED)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_vacio_devuelve_lista_vacia(session):
    """listar() con BD vacía devuelve una lista vacía (no None ni error)."""
    repo = ExamenContenidoSqlRepository(session)
    resultado = await repo.listar()
    assert resultado == [], f"Se esperaba [] pero se obtuvo {resultado!r}"


# ---------------------------------------------------------------------------
# GREEN: tests con un examen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_devuelve_examen_guardado(session):
    """listar() devuelve el examen guardado con id, titulo y cantidad_preguntas."""
    repo = ExamenContenidoSqlRepository(session)
    examen = await repo.guardar(_examen_con_n_preguntas("Parcial de Física", 3))
    await session.flush()

    resultado = await repo.listar()

    titulos = [r.titulo for r in resultado]
    assert "Parcial de Física" in titulos

    item = next(r for r in resultado if r.titulo == "Parcial de Física")
    assert item.id == examen.id
    assert item.cantidad_preguntas == 3


@pytest.mark.asyncio
async def test_listar_resumen_no_carga_preguntas_ni_opciones(session):
    """listar() devuelve solo id, titulo, cantidad_preguntas — no las preguntas completas."""
    repo = ExamenContenidoSqlRepository(session)
    await repo.guardar(_examen_con_n_preguntas("Examen de Matemática", 2))
    await session.flush()

    resultado = await repo.listar()

    for item in resultado:
        # El resumen NO debe tener atributo preguntas ni opciones
        assert not hasattr(item, "preguntas"), "listar() no debe cargar preguntas completas"
        assert hasattr(item, "cantidad_preguntas"), "listar() debe incluir cantidad_preguntas"


# ---------------------------------------------------------------------------
# TRIANGULATE: múltiples exámenes, orden alfabético
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_varios_examenes_orden_alfabetico(session):
    """listar() con varios exámenes retorna en orden alfabético ascendente por título."""
    repo = ExamenContenidoSqlRepository(session)
    # Insertar en orden inverso al esperado
    await repo.guardar(_examen_con_n_preguntas("Álgebra Lineal", 1))
    await repo.guardar(_examen_con_n_preguntas("Cálculo Diferencial", 2))
    await repo.guardar(_examen_con_n_preguntas("Biología General", 4))
    await session.flush()

    resultado = await repo.listar()

    titulos = [r.titulo for r in resultado]
    # Verificar que los tres títulos nuevos están en la lista
    assert "Álgebra Lineal" in titulos
    assert "Biología General" in titulos
    assert "Cálculo Diferencial" in titulos

    # Verificar orden alfabético entre ellos
    idx_algebra = titulos.index("Álgebra Lineal")
    idx_bio = titulos.index("Biología General")
    idx_calculo = titulos.index("Cálculo Diferencial")
    assert idx_algebra < idx_bio < idx_calculo, (
        f"Orden esperado Álgebra < Biología < Cálculo, obtenido: "
        f"Álgebra={idx_algebra}, Biología={idx_bio}, Cálculo={idx_calculo}"
    )


@pytest.mark.asyncio
async def test_listar_cantidad_preguntas_exacta(session):
    """cantidad_preguntas refleja el número real de preguntas en la BD."""
    repo = ExamenContenidoSqlRepository(session)
    examen_5 = await repo.guardar(_examen_con_n_preguntas("Examen con 5 preguntas", 5))
    examen_1 = await repo.guardar(_examen_con_n_preguntas("Examen con 1 pregunta", 1))
    await session.flush()

    resultado = await repo.listar()

    item_5 = next((r for r in resultado if r.id == examen_5.id), None)
    item_1 = next((r for r in resultado if r.id == examen_1.id), None)

    assert item_5 is not None
    assert item_1 is not None
    assert item_5.cantidad_preguntas == 5, f"Se esperaban 5 preguntas, se obtuvo {item_5.cantidad_preguntas}"
    assert item_1.cantidad_preguntas == 1, f"Se esperaba 1 pregunta, se obtuvo {item_1.cantidad_preguntas}"
