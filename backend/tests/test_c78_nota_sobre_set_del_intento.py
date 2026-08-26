"""c-78 E-07 (task 15.2): la nota se calcula sobre las preguntas de CADA alumno.

Con sorteo por intento, "las preguntas de este examen" deja de ser un dato del
examen. Si el denominador siguiera siendo el pool entero, un alumno que contesta
bien sus 10 preguntas sacaría 10/30 en vez de 10/10.

Es la parte más delicada del cambio: acá se decide una nota real.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.sorteo_por_intento import (
    resolver_preguntas_del_intento,
)
from app.application.moodle.grade_calculator import (
    RespuestaAlumno,
    calcular_nota_academica,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
    PreguntaSesionModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

_TABLES = [
    "pregunta_sesion",
    "tramo_sorteo_examen",
    "proctoring_session",
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "categoria_pregunta",
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
                CategoriaPreguntaModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                PreguntaClozeBlankModel.__table__,
                ProctoringSessionModel.__table__,
                TramoSorteoExamenModel.__table__,
                PreguntaSesionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _examen(session: AsyncSession, *, pool: int, cantidad: int, modo: str) -> str:
    """Examen con ``pool`` preguntas de 2 opciones (la primera correcta).

    En modo sorteo, todas las del pool quedan sin marcar: el tramo decide.
    """
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"NOTA-{mid[:8]}"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'U1')"
        ),
        {"id": cat_id, "mid": mid},
    )
    examen_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido (id, titulo, nota_maxima, nota_aprobacion,"
            " modo_preguntas) VALUES (:id, 'Parcial', 10, 6, :modo)"
        ),
        {"id": examen_id, "modo": modo},
    )
    for i in range(pool):
        pid = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO pregunta_examen"
                " (id, examen_id, enunciado, tipo, orden, seleccionada, categoria_id)"
                " VALUES (:id, :eid, :e, 'multichoice', :o, :sel, :cid)"
            ),
            {
                "id": pid,
                "eid": examen_id,
                "e": f"P{i}",
                "o": i,
                "sel": modo == "fijo",
                "cid": cat_id,
            },
        )
        for j, correcta in enumerate([True, False]):
            await session.execute(
                text(
                    "INSERT INTO opcion_respuesta (id, pregunta_id, texto, es_correcta, orden)"
                    " VALUES (:id, :pid, :t, :c, :o)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "pid": pid,
                    "t": f"op{j}",
                    "c": correcta,
                    "o": j,
                },
            )
    if modo != "fijo":
        await session.execute(
            text(
                "INSERT INTO tramo_sorteo_examen"
                " (id, examen_id, categoria_id, incluir_subcategorias, cantidad, orden)"
                " VALUES (:id, :eid, :cid, true, :cant, 0)"
            ),
            {"id": str(uuid.uuid4()), "eid": examen_id, "cid": cat_id, "cant": cantidad},
        )
    await session.commit()
    return examen_id


async def _sesion(session: AsyncSession, examen_id: str) -> str:
    sid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO proctoring_session (id, modo, examen_contenido_id)"
            " VALUES (:id, 'examen', :eid)"
        ),
        {"id": sid, "eid": examen_id},
    )
    await session.commit()
    return sid


async def _responder(
    session: AsyncSession, pregunta_ids: list[str], *, correctas: int
) -> list[RespuestaAlumno]:
    """Arma las respuestas: las primeras ``correctas`` bien, el resto mal."""
    respuestas: list[RespuestaAlumno] = []
    for i, pid in enumerate(pregunta_ids):
        fila = await session.execute(
            text(
                "SELECT id::text FROM opcion_respuesta"
                " WHERE pregunta_id = :pid AND es_correcta = :ok"
            ),
            {"pid": pid, "ok": i < correctas},
        )
        respuestas.append(
            RespuestaAlumno(pregunta_id=pid, opcion_elegida_id=fila.scalar_one())
        )
    return respuestas


@pytest.mark.asyncio
async def test_el_denominador_es_el_set_del_alumno_no_el_pool(session: AsyncSession):
    """RED→GREEN: 10 de 10 bien sobre un pool de 30 es un 10, no un 3,33."""
    examen_id = await _examen(session, pool=30, cantidad=10, modo="sorteo_por_intento")
    sid = await _sesion(session, examen_id)

    mias = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()
    respuestas = await _responder(session, mias, correctas=10)

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=respuestas,
        session_id=sid,
    )
    assert nota == 10.0


@pytest.mark.asyncio
async def test_media_bien_da_la_mitad_de_la_nota(session: AsyncSession):
    """TRIANGULATE: 5 de 10 sobre nota máxima 10 da 5."""
    examen_id = await _examen(session, pool=30, cantidad=10, modo="sorteo_por_intento")
    sid = await _sesion(session, examen_id)

    mias = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()
    respuestas = await _responder(session, mias, correctas=5)

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=respuestas,
        session_id=sid,
    )
    assert nota == 5.0


@pytest.mark.asyncio
async def test_dos_alumnos_con_sets_distintos_se_califican_cada_uno_sobre_el_suyo(
    session: AsyncSession,
):
    """El punto del cambio: cada uno rinde otra cosa y los dos sacan 10."""
    examen_id = await _examen(session, pool=30, cantidad=10, modo="sorteo_por_intento")
    sid_a = await _sesion(session, examen_id)
    sid_b = await _sesion(session, examen_id)

    de_a = await resolver_preguntas_del_intento(
        db=session, session_id=sid_a, examen_contenido_id=examen_id
    )
    de_b = await resolver_preguntas_del_intento(
        db=session, session_id=sid_b, examen_contenido_id=examen_id
    )
    await session.commit()
    assert set(de_a) != set(de_b)

    nota_a = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=await _responder(session, de_a, correctas=10),
        session_id=sid_a,
    )
    nota_b = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=await _responder(session, de_b, correctas=10),
        session_id=sid_b,
    )
    assert nota_a == nota_b == 10.0


@pytest.mark.asyncio
async def test_responder_una_pregunta_que_no_le_toco_no_suma(session: AsyncSession):
    """Blindaje: mandar respuestas de preguntas ajenas al intento no infla la nota.

    El cliente es un sensor no confiable (regla dura #6): el set del intento manda,
    no lo que llegue en el body.
    """
    examen_id = await _examen(session, pool=30, cantidad=10, modo="sorteo_por_intento")
    sid = await _sesion(session, examen_id)

    mias = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    ajenas = await session.execute(
        text(
            "SELECT id::text FROM pregunta_examen"
            " WHERE examen_id = :eid AND id::text != ALL(:mias) LIMIT 5"
        ),
        {"eid": examen_id, "mias": mias},
    )
    ids_ajenas = [r[0] for r in ajenas.fetchall()]
    assert ids_ajenas

    respuestas = await _responder(session, mias, correctas=5)
    respuestas += await _responder(session, ids_ajenas, correctas=len(ids_ajenas))

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=respuestas,
        session_id=sid,
    )
    # 5 de 10, no 10 de 15 ni 10 de 10.
    assert nota == 5.0


@pytest.mark.asyncio
async def test_modo_fijo_sigue_calculando_igual_que_antes(session: AsyncSession):
    """Compat: un examen 'fijo' se califica sobre `seleccionada`, como siempre."""
    examen_id = await _examen(session, pool=8, cantidad=0, modo="fijo")
    sid = await _sesion(session, examen_id)

    todas = await session.execute(
        text(
            "SELECT id::text FROM pregunta_examen WHERE examen_id = :eid ORDER BY orden"
        ),
        {"eid": examen_id},
    )
    ids = [r[0] for r in todas.fetchall()]
    respuestas = await _responder(session, ids, correctas=4)

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=respuestas,
        session_id=sid,
    )
    assert nota == 5.0


@pytest.mark.asyncio
async def test_sin_session_id_sigue_calculando_por_seleccionada(session: AsyncSession):
    """Compat de firma: los llamadores que todavía no pasan `session_id` no se rompen."""
    examen_id = await _examen(session, pool=8, cantidad=0, modo="fijo")

    todas = await session.execute(
        text(
            "SELECT id::text FROM pregunta_examen WHERE examen_id = :eid ORDER BY orden"
        ),
        {"eid": examen_id},
    )
    ids = [r[0] for r in todas.fetchall()]

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=examen_id,
        respuestas=await _responder(session, ids, correctas=8),
    )
    assert nota == 10.0
