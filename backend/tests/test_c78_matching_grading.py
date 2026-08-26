"""C-78: calificación de blanks tipo "matching" (emparejamiento).

matching se normaliza a cloze (ver moodle_parser._parse_matching) — cada par
estímulo/respuesta es un blank tipo="matching" que se resuelve por id, igual
que un blank multichoice (grade_calculator._BLANK_ELIGE_OPCION). Este test
verifica esa rama de grading contra DB real (regla dura #4).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.grade_calculator import RespuestaAlumno, calcular_nota_academica
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    MateriaModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)

_TABLES = [
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                PreguntaClozeBlankModel.__table__,
                OpcionClozeBlancoModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def examen_matching(session: AsyncSession):
    """Examen con una pregunta matching de 3 pares (3 blanks tipo='matching').

    Cada blank tiene 3 opciones (el pool completo de respuestas), con
    exactamente una marcada correcta — la de SU par.
    """
    examen_id = str(uuid.uuid4())
    pregunta_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": "Examen Matching Test"},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada)"
            " VALUES (:id, :eid, :e, 'cloze', 0, true)"
        ),
        {"id": pregunta_id, "eid": examen_id, "e": "Une cada lenguaje con su paradigma"},
    )

    pool = ["Multiparadigma", "Funcional", "Logico"]
    blank_ids = []
    opcion_ids_por_blank = []  # lista de {texto: id} por blank
    for i in range(3):
        blank_id = str(uuid.uuid4())
        blank_ids.append(blank_id)
        await session.execute(
            text(
                "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo)"
                " VALUES (:id, :pid, :o, 'matching')"
            ),
            {"id": blank_id, "pid": pregunta_id, "o": i},
        )
        ids_por_texto = {}
        for texto in pool:
            opcion_id = str(uuid.uuid4())
            ids_por_texto[texto] = opcion_id
            await session.execute(
                text(
                    "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso)"
                    " VALUES (:id, :bid, :t, :correcta, :peso)"
                ),
                {
                    "id": opcion_id,
                    "bid": blank_id,
                    "t": texto,
                    "correcta": texto == pool[i],
                    "peso": 100 if texto == pool[i] else 0,
                },
            )
        opcion_ids_por_blank.append(ids_por_texto)
    await session.commit()

    return {
        "examen_id": examen_id,
        "pregunta_id": pregunta_id,
        "blank_ids": blank_ids,
        "opcion_ids_por_blank": opcion_ids_por_blank,
        "pool": pool,
    }


@pytest.mark.asyncio
async def test_matching_todos_los_pares_correctos_nota_plena(
    session: AsyncSession, examen_matching: dict
):
    """RED→GREEN: elegir la opción correcta (por id) en los 3 pares → nota 100."""
    datos = examen_matching
    respuesta_cloze = {
        datos["blank_ids"][i]: datos["opcion_ids_por_blank"][i][datos["pool"][i]]
        for i in range(3)
    }

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(pregunta_id=datos["pregunta_id"], respuesta_cloze=respuesta_cloze)
        ],
    )

    assert nota == pytest.approx(100.0, abs=0.01), f"Esperaba 100.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_matching_un_par_cambiado_nota_parcial(
    session: AsyncSession, examen_matching: dict
):
    """TRIANGULATE: 2 de 3 pares correctos → nota 66.67 (2/3 * 100)."""
    datos = examen_matching
    pool = datos["pool"]
    respuesta_cloze = {
        datos["blank_ids"][0]: datos["opcion_ids_por_blank"][0][pool[0]],
        datos["blank_ids"][1]: datos["opcion_ids_por_blank"][1][pool[1]],
        # blank 2: elige la opción del par 0 (incorrecta para el par 2)
        datos["blank_ids"][2]: datos["opcion_ids_por_blank"][2][pool[0]],
    }

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(pregunta_id=datos["pregunta_id"], respuesta_cloze=respuesta_cloze)
        ],
    )

    assert nota == pytest.approx(66.67, abs=0.01), f"Esperaba 66.67, obtuvo {nota}"


@pytest.mark.asyncio
async def test_matching_sin_responder_nota_cero(
    session: AsyncSession, examen_matching: dict
):
    """TRIANGULATE: dict vacío → todos los pares incorrectos → nota 0."""
    datos = examen_matching

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[RespuestaAlumno(pregunta_id=datos["pregunta_id"], respuesta_cloze={})],
    )

    assert nota == pytest.approx(0.0, abs=0.01), f"Esperaba 0.0, obtuvo {nota}"
