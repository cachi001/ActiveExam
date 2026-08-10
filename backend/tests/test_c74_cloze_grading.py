"""C-74 §6 RED -> GREEN -> TRIANGULATE: calificación de preguntas cloze.

Cubre:
  6.1 Rama cloze en calcular_nota_academica: RespuestaAlumno.respuesta_cloze.
  6.2 Pregunta cloze con 4 blanks, 3 correctos → nota 75% del peso.
  6.3 Blank sin respuesta (dict vacío o clave ausente) → incorrecto, no rompe.

Tests contra DB real (proctoring_test). Sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.grade_calculator import (
    RespuestaAlumno,
    calcular_nota_academica,
)
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
async def examen_cloze(session: AsyncSession):
    """Crea un examen con una pregunta cloze de 4 blanks.

    Blanks:
      blank_0: opciones [correcta_0, incorrecta_0]
      blank_1: opciones [correcta_1, incorrecta_1]
      blank_2: opciones [correcta_2, incorrecta_2]
      blank_3: opciones [correcta_3, incorrecta_3]

    Devuelve un dict con los ids necesarios para los tests.
    """
    materia_id = str(uuid.uuid4())
    examen_id = str(uuid.uuid4())
    pregunta_id = str(uuid.uuid4())

    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": materia_id, "c": f"GR-{materia_id[:8]}", "n": "Grading Test"},
    )
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": "Examen Cloze Test"},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada)"
            " VALUES (:id, :eid, :e, 'cloze', 0, true)"
        ),
        {"id": pregunta_id, "eid": examen_id, "e": "Complete: ___ ___ ___ ___"},
    )
    await session.commit()

    blank_ids = []
    correct_opcion_ids = []
    wrong_opcion_ids = []

    for i in range(4):
        blank_id = str(uuid.uuid4())
        blank_ids.append(blank_id)
        await session.execute(
            text(
                "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo)"
                " VALUES (:id, :pid, :o, 'multichoice')"
            ),
            {"id": blank_id, "pid": pregunta_id, "o": i},
        )

        correct_id = str(uuid.uuid4())
        wrong_id = str(uuid.uuid4())
        correct_opcion_ids.append(correct_id)
        wrong_opcion_ids.append(wrong_id)

        await session.execute(
            text(
                "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso)"
                " VALUES (:id, :bid, :t, true, 100)"
            ),
            {"id": correct_id, "bid": blank_id, "t": f"Correcto {i}"},
        )
        await session.execute(
            text(
                "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso)"
                " VALUES (:id, :bid, :t, false, 0)"
            ),
            {"id": wrong_id, "bid": blank_id, "t": f"Incorrecto {i}"},
        )

    await session.commit()

    return {
        "examen_id": examen_id,
        "pregunta_id": pregunta_id,
        "blank_ids": blank_ids,
        "correct_opcion_ids": correct_opcion_ids,
        "wrong_opcion_ids": wrong_opcion_ids,
    }


# ---------------------------------------------------------------------------
# 6.1 Test: RespuestaAlumno acepta respuesta_cloze
# ---------------------------------------------------------------------------


def test_6_1_respuesta_alumno_acepta_cloze():
    """6.1 RED->GREEN: RespuestaAlumno puede llevar respuesta_cloze."""
    resp = RespuestaAlumno(
        pregunta_id="p1",
        respuesta_cloze={"blank1": "opcion1", "blank2": "opcion2"},
    )
    assert resp.respuesta_cloze == {"blank1": "opcion1", "blank2": "opcion2"}
    assert resp.opcion_elegida_id == ""


def test_6_1b_respuesta_alumno_sin_cloze_funciona_igual():
    """6.1 TRIANGULATE: RespuestaAlumno sin cloze sigue funcionando."""
    resp = RespuestaAlumno(pregunta_id="p1", opcion_elegida_id="opcion123")
    assert resp.respuesta_cloze is None
    assert resp.opcion_elegida_id == "opcion123"


# ---------------------------------------------------------------------------
# 6.2 Test: 4 blanks, 3 correctos → 75% del peso de esa pregunta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_6_2_cloze_3_de_4_correctos_nota_parcial(
    session: AsyncSession, examen_cloze: dict
):
    """6.2 GREEN: cloze 4 blanks, 3 correctos → nota 75% (75.0 sobre 100)."""
    datos = examen_cloze
    blank_ids = datos["blank_ids"]
    correct_ids = datos["correct_opcion_ids"]
    wrong_ids = datos["wrong_opcion_ids"]

    # 3 correctos, 1 incorrecto (el último blank elige la opción incorrecta)
    respuesta_cloze = {
        blank_ids[0]: correct_ids[0],
        blank_ids[1]: correct_ids[1],
        blank_ids[2]: correct_ids[2],
        blank_ids[3]: wrong_ids[3],  # incorrecto
    }

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(
                pregunta_id=datos["pregunta_id"],
                respuesta_cloze=respuesta_cloze,
            )
        ],
    )

    # 1 pregunta en el examen, 3/4 blanks correctos → contribución 0.75 preguntas
    # nota = (0.75 / 1) * 100 = 75.0
    assert nota == pytest.approx(75.0, abs=0.01), f"Esperaba 75.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_6_2b_cloze_todos_correctos_nota_plena(
    session: AsyncSession, examen_cloze: dict
):
    """6.2 TRIANGULATE: todos los blanks correctos → nota completa 100.0."""
    datos = examen_cloze
    blank_ids = datos["blank_ids"]
    correct_ids = datos["correct_opcion_ids"]

    respuesta_cloze = {blank_ids[i]: correct_ids[i] for i in range(4)}

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(
                pregunta_id=datos["pregunta_id"],
                respuesta_cloze=respuesta_cloze,
            )
        ],
    )

    assert nota == pytest.approx(100.0, abs=0.01), f"Esperaba 100.0, obtuvo {nota}"


# ---------------------------------------------------------------------------
# 6.3 Test: blank sin respuesta → incorrecto, no rompe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_6_3_blank_sin_respuesta_cuenta_como_incorrecto(
    session: AsyncSession, examen_cloze: dict
):
    """6.3 GREEN: dict vacío → todos incorrectos → nota 0."""
    datos = examen_cloze

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(
                pregunta_id=datos["pregunta_id"],
                respuesta_cloze={},  # dict vacío = todos incorrectos
            )
        ],
    )

    assert nota == pytest.approx(0.0, abs=0.01), f"Esperaba 0.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_6_3b_clave_ausente_cuenta_como_incorrecto(
    session: AsyncSession, examen_cloze: dict
):
    """6.3 TRIANGULATE: clave ausente para un blank → ese blank incorrecto."""
    datos = examen_cloze
    blank_ids = datos["blank_ids"]
    correct_ids = datos["correct_opcion_ids"]

    # Solo responde 2 de 4 blanks (los otros 2 ausentes = incorrectos)
    respuesta_cloze = {
        blank_ids[0]: correct_ids[0],
        blank_ids[1]: correct_ids[1],
        # blank_ids[2] y [3] ausentes
    }

    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(
                pregunta_id=datos["pregunta_id"],
                respuesta_cloze=respuesta_cloze,
            )
        ],
    )

    # 2/4 blanks correctos → contribución 0.5 → nota 50.0
    assert nota == pytest.approx(50.0, abs=0.01), f"Esperaba 50.0, obtuvo {nota}"


# ---------------------------------------------------------------------------
# Blanks SHORTANSWER: el alumno escribe TEXTO, no elige un id de opción
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def examen_cloze_shortanswer(session: AsyncSession):
    """Examen con una cloze de 2 blanks SHORTANSWER.

    blank_0 acepta 'len' o 'length'; blank_1 acepta 'entero'.
    """
    examen_id = str(uuid.uuid4())
    pregunta_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": examen_id, "t": "Examen Cloze Shortanswer"},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada)"
            " VALUES (:id, :eid, :e, 'cloze', 0, true)"
        ),
        {"id": pregunta_id, "eid": examen_id, "e": "La funcion ___ devuelve un ___"},
    )

    blank_ids = []
    for orden, aceptadas in enumerate((("len", "length"), ("entero",))):
        blank_id = str(uuid.uuid4())
        blank_ids.append(blank_id)
        await session.execute(
            text(
                "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo)"
                " VALUES (:id, :pid, :o, 'shortanswer')"
            ),
            {"id": blank_id, "pid": pregunta_id, "o": orden},
        )
        for texto in aceptadas:
            await session.execute(
                text(
                    "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso)"
                    " VALUES (:id, :bid, :t, true, 100)"
                ),
                {"id": str(uuid.uuid4()), "bid": blank_id, "t": texto},
            )
        await session.execute(
            text(
                "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso)"
                " VALUES (:id, :bid, 'nada', false, 0)"
            ),
            {"id": str(uuid.uuid4()), "bid": blank_id},
        )
    await session.commit()

    return {"examen_id": examen_id, "pregunta_id": pregunta_id, "blank_ids": blank_ids}


async def _nota_shortanswer(session, datos: dict, respuesta: dict[str, str]) -> float:
    return await calcular_nota_academica(
        db=session,
        examen_contenido_id=datos["examen_id"],
        respuestas=[
            RespuestaAlumno(
                pregunta_id=datos["pregunta_id"], respuesta_cloze=respuesta
            )
        ],
    )


@pytest.mark.asyncio
async def test_shortanswer_texto_escrito_se_corrige_por_texto(
    session: AsyncSession, examen_cloze_shortanswer: dict
):
    """RED: en un SHORTANSWER el alumno manda TEXTO, no un id — debe valer."""
    datos = examen_cloze_shortanswer
    b0, b1 = datos["blank_ids"]

    nota = await _nota_shortanswer(session, datos, {b0: "len", b1: "entero"})

    assert nota == pytest.approx(100.0, abs=0.01), f"Esperaba 100.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_shortanswer_ignora_mayusculas_y_espacios(
    session: AsyncSession, examen_cloze_shortanswer: dict
):
    """TRIANGULATE: Moodle corrige el shortanswer sin distinguir may/min ni bordes."""
    datos = examen_cloze_shortanswer
    b0, b1 = datos["blank_ids"]

    nota = await _nota_shortanswer(session, datos, {b0: "  LEN ", b1: "Entero"})

    assert nota == pytest.approx(100.0, abs=0.01), f"Esperaba 100.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_shortanswer_acepta_cualquier_respuesta_valida(
    session: AsyncSession, examen_cloze_shortanswer: dict
):
    """TRIANGULATE: un blank con varias correctas (=len~=length) acepta ambas."""
    datos = examen_cloze_shortanswer
    b0, b1 = datos["blank_ids"]

    nota = await _nota_shortanswer(session, datos, {b0: "length", b1: "entero"})

    assert nota == pytest.approx(100.0, abs=0.01), f"Esperaba 100.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_shortanswer_texto_incorrecto_no_suma(
    session: AsyncSession, examen_cloze_shortanswer: dict
):
    """TRIANGULATE: texto que coincide con una opción incorrecta no suma."""
    datos = examen_cloze_shortanswer
    b0, b1 = datos["blank_ids"]

    nota = await _nota_shortanswer(session, datos, {b0: "nada", b1: "entero"})

    # 1 de 2 blanks correctos → 50.0
    assert nota == pytest.approx(50.0, abs=0.01), f"Esperaba 50.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_shortanswer_texto_desconocido_no_suma(
    session: AsyncSession, examen_cloze_shortanswer: dict
):
    """TRIANGULATE borde: texto que no coincide con nada cuenta incorrecto."""
    datos = examen_cloze_shortanswer
    b0, b1 = datos["blank_ids"]

    nota = await _nota_shortanswer(session, datos, {b0: "cualquiera", b1: ""})

    assert nota == pytest.approx(0.0, abs=0.01), f"Esperaba 0.0, obtuvo {nota}"
