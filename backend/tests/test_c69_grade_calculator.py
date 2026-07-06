"""7.1 RED → 7.2 GREEN: tests del servicio de cálculo de nota académica.

Tests contra DB real (DATABASE_URL requerida). El servicio lee es_correcta
server-side desde la tabla opcion_respuesta — D3 (opción correcta NUNCA al cliente).

L2.5: la nota es sólo de respuestas correctas. Sin proctoring score.
"""

from __future__ import annotations

import os

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
    OpcionRespuestaModel,
    PreguntaExamenModel,
)

_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido")


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
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _crear_examen_con_2_preguntas(db: AsyncSession) -> tuple[str, str, str, str, str]:
    """Crea un examen de 2 preguntas multichoice; devuelve (examen_id, p1_id, p2_id, correcta1_id, correcta2_id)."""
    examen = ExamenContenidoModel(titulo="Parcial test")
    db.add(examen)
    await db.flush()

    p1 = PreguntaExamenModel(examen_id=examen.id, enunciado="Pregunta 1", tipo="multichoice", orden=0)
    p2 = PreguntaExamenModel(examen_id=examen.id, enunciado="Pregunta 2", tipo="multichoice", orden=1)
    db.add_all([p1, p2])
    await db.flush()

    o1_c = OpcionRespuestaModel(pregunta_id=p1.id, texto="Correcta", es_correcta=True, orden=0)
    o1_w = OpcionRespuestaModel(pregunta_id=p1.id, texto="Incorrecta", es_correcta=False, orden=1)
    o2_c = OpcionRespuestaModel(pregunta_id=p2.id, texto="Correcta", es_correcta=True, orden=0)
    o2_w = OpcionRespuestaModel(pregunta_id=p2.id, texto="Incorrecta", es_correcta=False, orden=1)
    db.add_all([o1_c, o1_w, o2_c, o2_w])
    await db.flush()

    return examen.id, p1.id, p2.id, o1_c.id, o2_c.id


# ---------------------------------------------------------------------------
# Tests 7.1 RED → 7.2 GREEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nota_perfecta_todas_correctas(session):
    """El alumno elige la opción correcta en todas las preguntas → nota 10."""
    examen_id, p1_id, p2_id, c1_id, c2_id = await _crear_examen_con_2_preguntas(session)

    respuestas = [
        RespuestaAlumno(pregunta_id=p1_id, opcion_elegida_id=c1_id),
        RespuestaAlumno(pregunta_id=p2_id, opcion_elegida_id=c2_id),
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_nota_cero_todas_incorrectas(session):
    """El alumno elige siempre la opción incorrecta → nota 0."""
    examen_id, p1_id, p2_id, c1_id, c2_id = await _crear_examen_con_2_preguntas(session)

    # Necesitamos las ids de las incorrectas — leemos del session
    from sqlalchemy import select

    res = await session.execute(
        select(OpcionRespuestaModel)
        .where(OpcionRespuestaModel.pregunta_id.in_([p1_id, p2_id]))
        .where(OpcionRespuestaModel.es_correcta.is_(False))
    )
    incorrectas = {r.pregunta_id: r.id for r in res.scalars().all()}

    respuestas = [
        RespuestaAlumno(pregunta_id=p1_id, opcion_elegida_id=incorrectas[p1_id]),
        RespuestaAlumno(pregunta_id=p2_id, opcion_elegida_id=incorrectas[p2_id]),
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_nota_parcial_mitad_correctas(session):
    """El alumno acierta la mitad → nota 5.0."""
    examen_id, p1_id, p2_id, c1_id, c2_id = await _crear_examen_con_2_preguntas(session)

    from sqlalchemy import select

    res = await session.execute(
        select(OpcionRespuestaModel)
        .where(OpcionRespuestaModel.pregunta_id == p2_id)
        .where(OpcionRespuestaModel.es_correcta.is_(False))
    )
    incorrecta_p2 = res.scalar_one().id

    respuestas = [
        RespuestaAlumno(pregunta_id=p1_id, opcion_elegida_id=c1_id),       # correcta
        RespuestaAlumno(pregunta_id=p2_id, opcion_elegida_id=incorrecta_p2),  # incorrecta
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_nota_cero_sin_respuestas(session):
    """Sin respuestas del alumno → nota 0 (no crash)."""
    examen_id, *_ = await _crear_examen_con_2_preguntas(session)

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=[]
    )

    assert nota == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_nota_cero_examen_inexistente(session):
    """Examen que no existe → nota 0 (no crash, no exception)."""
    nota = await calcular_nota_academica(
        db=session,
        examen_contenido_id="00000000-0000-0000-0000-000000000000",
        respuestas=[],
    )

    assert nota == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Opción B (pool): la nota considera SOLO las preguntas seleccionadas
# ---------------------------------------------------------------------------


async def _crear_examen_pool(
    db: AsyncSession,
) -> tuple[str, str, str, str, str, str]:
    """Examen con 2 seleccionadas + 1 deseleccionada.

    Devuelve (examen_id, p1_sel_id, p2_sel_id, p3_desel_id, c1_id, c3_id) donde
    c1/c3 son las opciones correctas de p1 (seleccionada) y p3 (deseleccionada).
    """
    examen = ExamenContenidoModel(titulo="Pool parcial")
    db.add(examen)
    await db.flush()

    p1 = PreguntaExamenModel(examen_id=examen.id, enunciado="Sel 1", tipo="multichoice", orden=0, seleccionada=True)
    p2 = PreguntaExamenModel(examen_id=examen.id, enunciado="Sel 2", tipo="multichoice", orden=1, seleccionada=True)
    p3 = PreguntaExamenModel(examen_id=examen.id, enunciado="Desel 3", tipo="multichoice", orden=2, seleccionada=False)
    db.add_all([p1, p2, p3])
    await db.flush()

    o1_c = OpcionRespuestaModel(pregunta_id=p1.id, texto="C", es_correcta=True, orden=0)
    o1_w = OpcionRespuestaModel(pregunta_id=p1.id, texto="W", es_correcta=False, orden=1)
    o2_c = OpcionRespuestaModel(pregunta_id=p2.id, texto="C", es_correcta=True, orden=0)
    o2_w = OpcionRespuestaModel(pregunta_id=p2.id, texto="W", es_correcta=False, orden=1)
    o3_c = OpcionRespuestaModel(pregunta_id=p3.id, texto="C", es_correcta=True, orden=0)
    o3_w = OpcionRespuestaModel(pregunta_id=p3.id, texto="W", es_correcta=False, orden=1)
    db.add_all([o1_c, o1_w, o2_c, o2_w, o3_c, o3_w])
    await db.flush()

    return examen.id, p1.id, p2.id, p3.id, o1_c.id, o3_c.id


@pytest.mark.asyncio
async def test_total_solo_cuenta_seleccionadas(session):
    """Opción B: el total ignora la deseleccionada.

    Alumno acierta la única seleccionada que responde (p1) → 1/2 seleccionadas = 5.0.
    La pregunta deseleccionada (p3) NO suma al total.
    """
    examen_id, p1_id, p2_id, p3_id, c1_id, c3_id = await _crear_examen_pool(session)

    respuestas = [
        RespuestaAlumno(pregunta_id=p1_id, opcion_elegida_id=c1_id),  # correcta, seleccionada
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_respuesta_a_deseleccionada_no_cuenta(session):
    """Opción B: acertar una pregunta deseleccionada NO suma correctas ni total.

    Alumno acierta p1 (seleccionada) y p3 (deseleccionada). Solo p1 cuenta:
    1 correcta / 2 seleccionadas = 5.0 (la correcta de p3 se ignora).
    """
    examen_id, p1_id, p2_id, p3_id, c1_id, c3_id = await _crear_examen_pool(session)

    respuestas = [
        RespuestaAlumno(pregunta_id=p1_id, opcion_elegida_id=c1_id),  # seleccionada, correcta
        RespuestaAlumno(pregunta_id=p3_id, opcion_elegida_id=c3_id),  # deseleccionada, correcta
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Redondeo a entero (ROUND_HALF_UP, como Moodle): la nota nunca es fraccionada
# ---------------------------------------------------------------------------


async def _crear_examen_n_preguntas(
    db: AsyncSession, n: int
) -> tuple[str, list[tuple[str, str]]]:
    """Crea un examen de ``n`` preguntas multichoice (todas seleccionadas).

    Devuelve (examen_id, [(pregunta_id, opcion_correcta_id), ...]).
    """
    examen = ExamenContenidoModel(titulo=f"Parcial {n} preguntas")
    db.add(examen)
    await db.flush()

    pares: list[tuple[str, str]] = []
    for i in range(n):
        p = PreguntaExamenModel(
            examen_id=examen.id, enunciado=f"P{i}", tipo="multichoice", orden=i
        )
        db.add(p)
        await db.flush()
        oc = OpcionRespuestaModel(pregunta_id=p.id, texto="C", es_correcta=True, orden=0)
        ow = OpcionRespuestaModel(pregunta_id=p.id, texto="W", es_correcta=False, orden=1)
        db.add_all([oc, ow])
        await db.flush()
        pares.append((p.id, oc.id))
    return examen.id, pares


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("n_preguntas", "n_correctas", "esperado"),
    [
        (20, 1, 1.0),   # 1/20*10 = 0.5 → 1 (half up). Antes mostraba 0.5 (sin sentido).
        (20, 3, 2.0),   # 3/20*10 = 1.5 → 2 (half up)
        (20, 11, 6.0),  # 11/20*10 = 5.5 → 6 (half up) → aprueba con nota_aprobacion=6
        (20, 13, 7.0),  # 13/20*10 = 6.5 → 7 (half up)
        (20, 20, 10.0), # perfecto
        (3, 1, 3.0),    # 1/3*10 = 3.33… → 3 (half down)
        (3, 2, 7.0),    # 2/3*10 = 6.66… → 7 (half up)
    ],
)
async def test_nota_redondea_a_entero_half_up(
    session, n_preguntas, n_correctas, esperado
):
    """La nota se redondea SIEMPRE a entero (ROUND_HALF_UP) — nunca fraccionada."""
    examen_id, pares = await _crear_examen_n_preguntas(session, n_preguntas)
    respuestas = [
        RespuestaAlumno(pregunta_id=pid, opcion_elegida_id=cid)
        for (pid, cid) in pares[:n_correctas]
    ]

    nota = await calcular_nota_academica(
        db=session, examen_contenido_id=examen_id, respuestas=respuestas
    )

    assert nota == pytest.approx(esperado)
    # La nota es un entero exacto (sin parte fraccionada).
    assert nota == int(nota)


# ---------------------------------------------------------------------------
# L2.5: la nota no incorpora score de proctoring (7.13)
# ---------------------------------------------------------------------------


def test_l2_5_nota_no_afectada_por_proctoring_score():
    """7.13 L2.5: calcular_nota_academica NO recibe ni usa score de proctoring.

    El servicio SÓLO recibe examen_contenido_id y respuestas.
    No existe parámetro de score ni flags de proctoring en su firma.
    Esta prueba verifica que la firma del servicio no acepte datos de proctoring.
    """
    import inspect

    from app.application.moodle.grade_calculator import calcular_nota_academica

    sig = inspect.signature(calcular_nota_academica)
    param_names = set(sig.parameters.keys())

    # La firma SÓLO debe tener: db, examen_contenido_id, respuestas
    assert "db" in param_names
    assert "examen_contenido_id" in param_names
    assert "respuestas" in param_names

    # NO debe tener parámetros de proctoring
    proctoring_params = {"score", "flags", "proctoring_score", "proctoring_flags", "eventos"}
    assert not (proctoring_params & param_names), (
        f"La firma de calcular_nota_academica contiene parámetros de proctoring: "
        f"{proctoring_params & param_names} — viola L2.5"
    )
