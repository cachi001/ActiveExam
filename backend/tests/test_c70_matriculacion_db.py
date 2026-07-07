"""Tests de matriculación por código contra DB real (C-70, sin mocks de DB).

Cubre los escenarios de las specs ``matriculacion-por-codigo`` y ``exam-content-model``:
autogeneración/unicidad del código, alta con código provisto, rechazo de duplicado,
auto-matriculación del alumno (happy / código inválido / idempotente), rotación sin
desmatricular, y coexistencia con la inscripción manual.

Requiere ``DATABASE_URL`` (Postgres real). Sin ella, se saltan (regla dura #4: base
real, nada de mocks de DB).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.errors import CodigoMatriculacionInvalidoError
from app.application.exam_content.inscripcion_service import AutoMatriculacionService
from app.application.exam_content.materia_comision_service import MateriaComisionService
from app.domain.exam_content.entities import Materia
from app.domain.exam_content.errors import CodigoMatriculacionDuplicadoError
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
    InscripcionSqlRepository,
    MateriaSqlRepository,
)

_TABLES = (InscripcionModel, ComisionModel, MateriaModel, UsuarioModel)


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
        for name in ("inscripcion", "comision", "materia", "usuario"):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[m.__table__ for m in _TABLES],
        )
    yield eng
    async with eng.begin() as conn:
        for name in ("inscripcion", "comision", "materia", "usuario"):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


# --- Helpers ---------------------------------------------------------------


def _svc(session) -> MateriaComisionService:
    return MateriaComisionService(
        materia_repo=MateriaSqlRepository(session),
        comision_repo=ComisionSqlRepository(session),
    )


def _auto(session) -> AutoMatriculacionService:
    return AutoMatriculacionService(
        comision_repo=ComisionSqlRepository(session),
        materia_repo=MateriaSqlRepository(session),
        inscripcion_repo=InscripcionSqlRepository(session),
    )


async def _crear_materia(session, codigo="PROG1") -> str:
    materia = await MateriaSqlRepository(session).guardar(
        Materia(codigo=codigo, nombre=f"Materia {codigo}")
    )
    await session.flush()
    return materia.id


async def _crear_alumno(session) -> str:
    uid = str(uuid.uuid4())
    session.add(
        UsuarioModel(
            id=uid,
            id_institucional=f"alu-{uid[:8]}",
            email=f"{uid[:8]}@uni.edu",
            roles=["estudiante"],
            attrs_federados={},
        )
    )
    await session.flush()
    return uid


# --- Alta de comisión: código autogenerado / provisto / duplicado ----------


@pytest.mark.asyncio
async def test_alta_sin_codigo_autogenera_unico(session):
    materia_id = await _crear_materia(session)
    comision = await _svc(session).crear_comision(
        materia_id=materia_id, codigo="C1", nombre="Comisión 1"
    )
    assert comision.codigo_matriculacion
    assert comision.codigo_matriculacion.startswith("PROG1-")


@pytest.mark.asyncio
async def test_alta_con_codigo_provisto_lo_usa_tal_cual(session):
    materia_id = await _crear_materia(session, "MATE2")
    comision = await _svc(session).crear_comision(
        materia_id=materia_id,
        codigo="C1",
        nombre="Comisión 1",
        codigo_matriculacion="MiCodigo-XyZ9",
    )
    assert comision.codigo_matriculacion == "MiCodigo-XyZ9"


@pytest.mark.asyncio
async def test_alta_con_codigo_duplicado_rechaza(session):
    materia_id = await _crear_materia(session, "DUP1")
    svc = _svc(session)
    await svc.crear_comision(
        materia_id=materia_id, codigo="C1", nombre="C1",
        codigo_matriculacion="REPETIDO-1",
    )
    with pytest.raises(CodigoMatriculacionDuplicadoError):
        await svc.crear_comision(
            materia_id=materia_id, codigo="C2", nombre="C2",
            codigo_matriculacion="REPETIDO-1",
        )


# --- Auto-matriculación del alumno -----------------------------------------


@pytest.mark.asyncio
async def test_inscribir_por_codigo_happy(session):
    materia_id = await _crear_materia(session, "APP1")
    comision = await _svc(session).crear_comision(
        materia_id=materia_id, codigo="C1", nombre="Comisión 1",
        codigo_matriculacion="APP1-JOIN",
    )
    alumno = await _crear_alumno(session)

    result = await _auto(session).inscribir_por_codigo("APP1-JOIN", alumno)
    assert result.ya_inscripto is False
    assert result.comision_id == comision.id
    assert result.materia_nombre == "Materia APP1"
    assert await InscripcionSqlRepository(session).existe(alumno, comision.id)


@pytest.mark.asyncio
async def test_inscribir_por_codigo_inexistente_rechaza_sin_crear(session):
    alumno = await _crear_alumno(session)
    with pytest.raises(CodigoMatriculacionInvalidoError):
        await _auto(session).inscribir_por_codigo("NO-EXISTE", alumno)


@pytest.mark.asyncio
async def test_inscribir_por_codigo_idempotente(session):
    materia_id = await _crear_materia(session, "IDEM1")
    comision = await _svc(session).crear_comision(
        materia_id=materia_id, codigo="C1", nombre="C1",
        codigo_matriculacion="IDEM1-K",
    )
    alumno = await _crear_alumno(session)
    auto = _auto(session)

    primero = await auto.inscribir_por_codigo("IDEM1-K", alumno)
    assert primero.ya_inscripto is False
    segundo = await auto.inscribir_por_codigo("IDEM1-K", alumno)
    assert segundo.ya_inscripto is True  # no duplica, respuesta amistosa
    assert segundo.comision_id == comision.id


# --- Rotación del código ----------------------------------------------------


@pytest.mark.asyncio
async def test_rotar_codigo_genera_nuevo_y_no_desmatricula(session):
    materia_id = await _crear_materia(session, "ROT1")
    svc = _svc(session)
    comision = await svc.crear_comision(
        materia_id=materia_id, codigo="C1", nombre="C1",
        codigo_matriculacion="ROT1-OLD",
    )
    alumno = await _crear_alumno(session)
    await _auto(session).inscribir_por_codigo("ROT1-OLD", alumno)

    rotada = await svc.rotar_codigo_matriculacion(comision.id)
    assert rotada.codigo_matriculacion != "ROT1-OLD"
    assert rotada.codigo_matriculacion.startswith("ROT1-")
    # La inscripción existente sobrevive a la rotación.
    assert await InscripcionSqlRepository(session).existe(alumno, comision.id)


# --- Coexistencia con inscripción manual -----------------------------------


@pytest.mark.asyncio
async def test_inscripcion_manual_coexiste_y_codigo_no_duplica(session):
    materia_id = await _crear_materia(session, "COEX1")
    comision = await _svc(session).crear_comision(
        materia_id=materia_id, codigo="C1", nombre="C1",
        codigo_matriculacion="COEX1-J",
    )
    alumno = await _crear_alumno(session)

    # Camino manual (C-69) sigue funcionando.
    await InscripcionSqlRepository(session).inscribir(alumno, comision.id)
    # Luego el mismo alumno usa el código: idempotente, no duplica.
    result = await _auto(session).inscribir_por_codigo("COEX1-J", alumno)
    assert result.ya_inscripto is True
