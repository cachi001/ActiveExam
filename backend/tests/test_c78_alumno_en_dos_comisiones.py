"""c-78 — Qué pasa si un alumno consigue el código de DOS comisiones de la misma materia.

Pregunta del dueño (26/8/2026). El código de matriculación lo comparte el docente
y no es secreto: un alumno puede conseguir el de otra comisión y usarlo.

Este módulo documenta el comportamiento REAL, sin suponerlo. Lo que importa no es
la matrícula en sí (estar en dos comisiones podría ser legítimo: recursante,
cambio de comisión a mitad de cuatrimestre) sino lo que arrastra: bajo el modelo
REPLICADO de c-78 §14.1, cada comisión tiene su **propia réplica** del mismo
examen. Un alumno en dos comisiones ve DOS exámenes que son el mismo parcial, y
puede rendir los dos.

Y esas réplicas comparten `moodle_courseid`/`cmid` (§14.1: en el campus hay UNA
aula por materia y las comisiones son grupos dentro), así que las dos notas se
escriben en el MISMO destino para el MISMO alumno: la segunda pisa a la primera.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel  # noqa: F401
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401

_TABLES = [
    "inscripcion",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
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
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                MateriaCoordinadorModel.__table__,
                ComisionModel.__table__,
                ComisionTutorModel.__table__,
                ExamenContenidoModel.__table__,
                InscripcionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _materia_con_dos_comisiones(factory) -> tuple[str, str, str, str, str]:
    """Materia + C1 + C2 + una réplica del MISMO parcial en cada una."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()

        c1 = ComisionModel(
            materia_id=materia.id, codigo=f"C1-{sufijo}", nombre="Comisión 1",
            codigo_matriculacion=f"K1-{sufijo}",
        )
        c2 = ComisionModel(
            materia_id=materia.id, codigo=f"C2-{sufijo}", nombre="Comisión 2",
            codigo_matriculacion=f"K2-{sufijo}",
        )
        s.add_all([c1, c2])
        await s.flush()

        # Las dos réplicas del mismo parcial, con el MISMO destino en Moodle.
        e1 = ExamenContenidoModel(
            titulo=f"Parcial 1 ({c1.codigo})", comision_id=c1.id,
            moodle_courseid=7, moodle_cmid=1509,
        )
        e2 = ExamenContenidoModel(
            titulo=f"Parcial 1 ({c2.codigo})", comision_id=c2.id,
            moodle_courseid=7, moodle_cmid=1509,
        )
        s.add_all([e1, e2])
        await s.flush()
        ids = (materia.id, c1.id, c2.id, e1.id, e2.id)
        await s.commit()
    return ids


async def _alumno(factory) -> str:
    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"alu-{sufijo}",
            email=f"alu-{sufijo}@test.local",
            roles=["estudiante"],
            password_hash="!sin-password",
            nombre="Alumno",
            apellido="Doble",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


@pytest.mark.asyncio
async def test_un_alumno_puede_quedar_en_dos_comisiones_de_la_misma_materia(factory):
    """La matrícula NO lo impide: no hay unicidad por (usuario, materia).

    Puede ser legítimo (recursante, cambio de comisión), así que el hecho en sí
    no es el problema. El problema es lo que arrastra — ver el test siguiente.
    """
    _m, c1, c2, _e1, _e2 = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)

    async with factory() as s:
        s.add(InscripcionModel(usuario_id=alumno, comision_id=c1))
        s.add(InscripcionModel(usuario_id=alumno, comision_id=c2))
        await s.commit()

    async with factory() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM inscripcion i "
                    "JOIN comision c ON c.id = i.comision_id "
                    "WHERE i.usuario_id = :u"
                ),
                {"u": alumno},
            )
        ).scalar_one()

    assert n == 2, "la base permite dos comisiones de la misma materia"


@pytest.mark.asyncio
async def test_queda_con_dos_examenes_que_son_el_mismo_parcial(factory):
    """LA CONSECUENCIA REAL, y por qué esto importa.

    Bajo el modelo replicado (§14.1) cada comisión tiene su propia copia del
    parcial. Un alumno en dos comisiones ve DOS exámenes que son el mismo, y
    puede rendir los dos: dos intentos donde la regla decía uno.

    Peor: las dos réplicas comparten `moodle_cmid`, así que las dos notas van al
    MISMO destino para el MISMO alumno y la segunda pisa a la primera.
    """
    _m, c1, c2, e1, e2 = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)

    async with factory() as s:
        s.add(InscripcionModel(usuario_id=alumno, comision_id=c1))
        s.add(InscripcionModel(usuario_id=alumno, comision_id=c2))
        await s.commit()

    async with factory() as s:
        filas = (
            await s.execute(
                text(
                    "SELECT e.id, e.titulo, e.moodle_cmid FROM examen_contenido e "
                    "JOIN inscripcion i ON i.comision_id = e.comision_id "
                    "WHERE i.usuario_id = :u AND e.eliminado_en IS NULL"
                ),
                {"u": alumno},
            )
        ).all()

    # str(): asyncpg devuelve UUID y los ids de la fixture son str.
    ids = {str(f[0]) for f in filas}
    cmids = {f[2] for f in filas}

    assert ids == {str(e1), str(e2)}, "el alumno ve las DOS réplicas del mismo parcial"
    assert len(cmids) == 1, (
        "las dos réplicas escriben la nota en el MISMO destino de Moodle: "
        "la segunda pisa a la primera"
    )
