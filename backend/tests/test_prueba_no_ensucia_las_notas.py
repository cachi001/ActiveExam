"""La rendición de prueba del docente no puede aparecer como una nota.

Es la mitad que importa de "probar el examen": destrabar la guarda de
inscripción es fácil, pero si la sesión del docente queda como una más, el
docente figura en la tabla de resultados con nota propia, cuenta en las
estadísticas y es candidato a que esa nota se publique en Moodle.

Los cuatro caminos que la tocan viven en `resultados_query`: el listado de
resultados, el cierre de sesiones colgadas, el cálculo de ausentes y la cola de
write-back. Este archivo los fija a la vez, porque el defecto no es de uno solo:
es "alguien agregó una consulta y se olvidó del filtro".

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

from app.application.moodle.resultados_query import (
    listar_estados_sincronizables,
    listar_resultados_examen,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.models.transactional import UsuarioModel

_TABLES = [
    "moodle_writeback_estado",
    "proctoring_session",
    "inscripcion",
    "examen_contenido",
    "comision",
    "materia",
    "usuario",
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
                UsuarioModel.__table__,
                InscripcionModel.__table__,
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


async def _examen_con_dos_rendiciones(db: AsyncSession) -> tuple[str, str, str]:
    """Un alumno de verdad y un docente probando. Devuelve (examen, alumno, prueba)."""
    mid = str(uuid.uuid4())
    await db.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"PRU-{mid[:8]}"},
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

    sufijo = eid[:8]
    ids: list[str] = []
    for base, es_prueba in (("alumno-1", False), ("profe-1", True)):
        idnumber = f"{base}-{sufijo}"
        # Inscriptos los dos: en la comisión de demo el profesor estaba en el
        # padrón, y es lo que destapó el bug del ausente falso.
        uid = str(uuid.uuid4())
        await db.execute(
            text(
                "INSERT INTO usuario (id, username, email, nombre, apellido,"
                " password_hash, roles)"
                " VALUES (:id, :u, :e, 'N', 'A', 'x', '[]'::jsonb)"
            ),
            {"id": uid, "u": idnumber, "e": f"{idnumber}@test.local"},
        )
        await db.execute(
            text(
                "INSERT INTO inscripcion (id, usuario_id, comision_id)"
                " VALUES (:id, :u, :c)"
            ),
            {"id": str(uuid.uuid4()), "u": uid, "c": cid},
        )
        sid = str(uuid.uuid4())
        await db.execute(
            text(
                "INSERT INTO proctoring_session"
                " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email,"
                "  creada_en, finalizada_en, es_prueba)"
                " VALUES (:id, :e, 'examen', :n, :m, :c, :f, :p)"
            ),
            {
                "id": sid,
                "e": eid,
                "n": idnumber,
                "m": f"{idnumber}@test.local",
                "c": datetime.now(timezone.utc),
                "f": datetime.now(timezone.utc),
                "p": es_prueba,
            },
        )
        await db.execute(
            text(
                "INSERT INTO moodle_writeback_estado (session_id, estado, nota)"
                " VALUES (:s, 'pendiente', 80)"
            ),
            {"s": sid},
        )
        ids.append(sid)
    await db.commit()
    return eid, ids[0], ids[1]


@pytest.mark.asyncio
async def test_la_prueba_no_aparece_en_la_tabla_de_resultados(db: AsyncSession):
    examen_id, sesion_alumno, _ = await _examen_con_dos_rendiciones(db)

    filas, total = await listar_resultados_examen(db=db, examen_id=examen_id)

    assert total == 1, "el docente no es un alumno del examen"
    assert [f.session_id for f in filas] == [sesion_alumno]


@pytest.mark.asyncio
async def test_la_prueba_no_entra_en_la_cola_de_publicacion_a_moodle(db: AsyncSession):
    """La consecuencia peor: publicarle al docente una nota en el campus real."""
    examen_id, sesion_alumno, _ = await _examen_con_dos_rendiciones(db)

    pendientes = await listar_estados_sincronizables(db=db, examen_id=examen_id)

    assert [str(p.session_id) for p in pendientes] == [sesion_alumno]


@pytest.mark.asyncio
async def test_quien_probo_el_examen_no_figura_como_ausente(db: AsyncSession):
    """El filtro de pruebas no puede convertir al docente en un ausente.

    Encontrado probando en el navegador: el profesor estaba inscripto en la
    comisión de demo, así que al dejar de contar su prueba como rendición pasó a
    aparecer en la tabla como ausente con nota 0. Para ausentes hay que mirar
    TODAS las sesiones, incluidas las de prueba: lo que la prueba no puede es
    tener nota, no "no existir".
    """
    examen_id, _, _ = await _examen_con_dos_rendiciones(db)

    rindieron = await db.execute(
        text(
            "SELECT alumno_idnumber FROM proctoring_session"
            " WHERE examen_contenido_id = :e"
        ),
        {"e": examen_id},
    )
    quienes = {f[0] for f in rindieron.all()}

    filas, _ = await listar_resultados_examen(db=db, examen_id=examen_id)
    ausentes = [f for f in filas if f.session_id is None]

    assert any(q.startswith("profe-1") for q in quienes)
    assert all(not (f.alumno_idnumber or "").startswith("profe-1") for f in ausentes), (
        "quien probó el examen no es un ausente"
    )
