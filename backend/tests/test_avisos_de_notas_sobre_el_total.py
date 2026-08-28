"""Los avisos de notas trabadas cuentan el EXAMEN, no la página que estás viendo.

Encontrado probando: arriba de la tabla dice "2 notas retenidas por revisión" y
"1 nota sin sincronizar por configuración". Esos números se calculaban en el
cliente sobre los items de la página, así que al pasar a la página 2 el primero
directamente desaparecía y el segundo cambiaba.

Es el mismo defecto que ya había mordido con los ausentes: un agregado sobre el
total no se puede calcular con una página en la mano. El docente decide a quién
ir a destrabar mirando ese número.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.resultados_query import listar_resultados_examen
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

_TABLES = [
    "moodle_writeback_estado",
    "proctoring_session",
    "examen_contenido",
    "comision",
    "materia",
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                ProctoringSessionModel.__table__,
                MoodleWritebackEstadoModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _examen_con_seis_notas(db: AsyncSession) -> str:
    """Seis rendiciones: dos anuladas y cuatro normales.

    Las dos anuladas caen en la primera página con page_size=5, que es
    exactamente lo que hacía parecer correcto el conteo viejo: al pasar a la
    página 2 el aviso desaparecía.

    Se usan anuladas y no sesiones en riesgo porque el riesgo sale del SCORE, y
    el score se calcula sobre los eventos: sembrarlos acá metería toda la
    mecánica de scoring en un test que es sobre el conteo.
    """
    mid = str(uuid.uuid4())
    await db.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"AVI-{mid[:8]}"},
    )
    cid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :m, :c, 'Comisión', :k)"
        ),
        {"id": cid, "m": mid, "c": f"C-{cid[:6]}", "k": f"K-{cid[:6]}"},
    )
    eid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO examen_contenido (id, comision_id, titulo, borrador)"
            " VALUES (:id, :c, 'Parcial', false)"
        ),
        {"id": eid, "c": cid},
    )

    decisiones = ["anulado", "anulado", None, None, None, None]
    for i, decision in enumerate(decisiones):
        sid = str(uuid.uuid4())
        await db.execute(
            text(
                "INSERT INTO proctoring_session"
                " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email,"
                "  creada_en, finalizada_en, decision, es_prueba)"
                " VALUES (:id, :e, 'examen', :n, :m, :c, :f, :d, false)"
            ),
            {
                "id": sid,
                "e": eid,
                "n": f"alumno-{i}",
                "m": f"alumno{i}@test.local",
                "c": datetime.now(timezone.utc),
                "f": datetime.now(timezone.utc),
                "d": decision,
            },
        )
        await db.execute(
            text(
                "INSERT INTO moodle_writeback_estado (session_id, estado, nota)"
                " VALUES (:s, 'pendiente', 80)"
            ),
            {"s": sid},
        )
    await db.commit()
    return eid


@pytest.mark.asyncio
async def test_los_avisos_no_cambian_al_pasar_de_pagina(db: AsyncSession):
    examen_id = await _examen_con_seis_notas(db)

    _, _, avisos_p1 = await listar_resultados_examen(
        db=db, examen_id=examen_id, page=1, page_size=5, con_avisos=True
    )
    _, _, avisos_p2 = await listar_resultados_examen(
        db=db, examen_id=examen_id, page=2, page_size=5, con_avisos=True
    )

    assert avisos_p1 == avisos_p2, "el aviso describe el examen, no la página"


@pytest.mark.asyncio
async def test_cuenta_las_trabadas_de_todo_el_examen(db: AsyncSession):
    """En la página 2 hay una sola fila y ninguna trabada: igual son 2."""
    examen_id = await _examen_con_seis_notas(db)

    _, _, avisos = await listar_resultados_examen(
        db=db, examen_id=examen_id, page=2, page_size=5, con_avisos=True
    )

    assert avisos["retenidas_por_revision"] == 2


@pytest.mark.asyncio
async def test_sin_pedirlos_no_se_pagan(db: AsyncSession):
    """El listado no tiene por qué pagar la consulta de agregados si no se usan."""
    examen_id = await _examen_con_seis_notas(db)

    filas, total, avisos = await listar_resultados_examen(
        db=db, examen_id=examen_id, page=1, page_size=5
    )

    assert total == 6
    assert len(filas) == 5
    assert avisos is None
