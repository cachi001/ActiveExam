"""El aviso previo a una baja tiene que decir a cuánta gente deja afuera.

## Por qué

Dar de baja una materia o una comisión BLOQUEA la rendición de todos sus
exámenes, y se permite aunque haya alumnos inscriptos: el único freno duro son
las sesiones en curso (ver `test_c78_baja_con_gente_rindiendo.py`). Eso está
bien — si los inscriptos bloquearan, una materia con historia no se podría
retirar nunca.

Lo que faltaba era avisarlo. `ImpactoBaja` contaba exámenes, comisiones y
rendiciones ya hechas, pero NO los inscriptos, así que la pantalla de
confirmación le pedía al admin que confirmara sin decirle a cuántos alumnos les
corta el acceso. Verificado el 28/8/2026 contra la base de desarrollo: una
materia con 4 inscriptos se dio de baja sin una sola mención de esos 4.

## Qué NO cambia

Los inscriptos siguen sin bloquear. Este conteo es para el aviso, igual que
`rendiciones`. La baja es lógica: las inscripciones quedan intactas y vuelven
con `reactivar`.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.impacto_baja import (
    impacto_baja_comision,
    impacto_baja_materia,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel

_TABLES_TO_DROP = [
    "inscripcion",
    "opcion_respuesta",
    "pregunta_examen",
    "proctoring_session",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
    "usuario",
]
_TABLES_TO_CREATE = [
    UsuarioModel.__table__,
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    InscripcionModel.__table__,
]


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
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _arbol_con_inscriptos(factory, *, inscriptos: int) -> tuple[str, str]:
    """Materia + comisión + examen + N alumnos inscriptos. Devuelve (materia, comisión)."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        s.add(ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id))
        for i in range(inscriptos):
            alumno = UsuarioModel(
                username=f"alu-{sufijo}-{i}",
                email=f"alu-{sufijo}-{i}@test.local",
                password_hash="x",
                roles=["estudiante"],
            )
            s.add(alumno)
            await s.flush()
            s.add(InscripcionModel(usuario_id=alumno.id, comision_id=comision.id))
        ids = (materia.id, comision.id)
        await s.commit()
    return ids


@pytest.mark.asyncio
async def test_la_baja_de_materia_cuenta_sus_inscriptos(factory):
    materia_id, _ = await _arbol_con_inscriptos(factory, inscriptos=4)
    async with factory() as s:
        impacto = await impacto_baja_materia(s, materia_id)
    assert impacto.inscriptos == 4


@pytest.mark.asyncio
async def test_la_baja_de_comision_cuenta_sus_inscriptos(factory):
    _, comision_id = await _arbol_con_inscriptos(factory, inscriptos=2)
    async with factory() as s:
        impacto = await impacto_baja_comision(s, comision_id)
    assert impacto.inscriptos == 2


@pytest.mark.asyncio
async def test_sin_inscriptos_no_inventa_ninguno(factory):
    """Triangulación: el aviso no puede alarmar por gente que no existe."""
    materia_id, _ = await _arbol_con_inscriptos(factory, inscriptos=0)
    async with factory() as s:
        impacto = await impacto_baja_materia(s, materia_id)
    assert impacto.inscriptos == 0


@pytest.mark.asyncio
async def test_no_cuenta_inscriptos_de_otra_materia(factory):
    """Cada baja avisa por SU gente: mezclarlas infla el aviso y lo vuelve ruido."""
    materia_a, _ = await _arbol_con_inscriptos(factory, inscriptos=3)
    await _arbol_con_inscriptos(factory, inscriptos=5)
    async with factory() as s:
        impacto = await impacto_baja_materia(s, materia_a)
    assert impacto.inscriptos == 3


@pytest.mark.asyncio
async def test_los_inscriptos_no_bloquean_la_baja(factory):
    """Siguen siendo un aviso, no un freno: el único freno es gente rindiendo.

    Si `sesiones_en_curso` empezara a contar inscriptos, una materia con
    historia no se podría retirar nunca.
    """
    materia_id, _ = await _arbol_con_inscriptos(factory, inscriptos=4)
    async with factory() as s:
        impacto = await impacto_baja_materia(s, materia_id)
    assert impacto.sesiones_en_curso == 0
