"""c-78 E-07 (tasks 15.1/15.2): sorteo de preguntas por intento.

El examen guarda la CONDICIÓN del sorteo (`tramo_sorteo_examen`) en vez de su
resultado, y el set concreto se resuelve al arrancar cada intento y se persiste en
`pregunta_sesion`. Cada alumno rinde preguntas distintas.

La diferencia deliberada con Moodle: el sorteo corre contra el POOL YA COPIADO en
el examen (`pregunta_examen`), no contra el banco vivo. Por eso mover, reclasificar
o borrar preguntas del banco no puede dejar a nadie sin examen.

Los exámenes en modo 'fijo' (todo lo que ya existe y todo lo importado de XML) no
cambian: siguen resolviéndose por `seleccionada`.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.sorteo_por_intento import (
    PoolInsuficienteError,
    resolver_preguntas_del_intento,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
    PreguntaSesionModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

_TABLES = [
    "pregunta_sesion",
    "tramo_sorteo_examen",
    "proctoring_session",
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
def factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def session(factory):
    async with factory() as s:
        yield s
        await s.rollback()


async def _examen_con_sorteo(
    session: AsyncSession,
    *,
    pool: int = 30,
    cantidad: int = 10,
    modo: str = "sorteo_por_intento",
) -> str:
    """Examen con un pool de ``pool`` preguntas y un tramo que sortea ``cantidad``.

    Todas las del pool quedan con seleccionada=False: en modo sorteo, quién entra lo
    decide el tramo por intento, no la marca del examen.
    """
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"SORT-{mid[:8]}", "n": "Materia Sorteo"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 1')"
        ),
        {"id": cat_id, "mid": mid},
    )

    examen_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido (id, titulo, nota_maxima, nota_aprobacion,"
            " modo_preguntas) VALUES (:id, 'Parcial sorteado', 10, 6, :modo)"
        ),
        {"id": examen_id, "modo": modo},
    )
    for i in range(pool):
        await session.execute(
            text(
                "INSERT INTO pregunta_examen"
                " (id, examen_id, enunciado, tipo, orden, seleccionada, categoria_id)"
                " VALUES (:id, :eid, :e, 'multichoice', :o, false, :cid)"
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": examen_id,
                "e": f"Pregunta {i}",
                "o": i,
                "cid": cat_id,
            },
        )
    await session.execute(
        text(
            "INSERT INTO tramo_sorteo_examen"
            " (id, examen_id, categoria_id, incluir_subcategorias, cantidad, orden)"
            " VALUES (:id, :eid, :cid, true, :cant, 0)"
        ),
        {
            "id": str(uuid.uuid4()),
            "eid": examen_id,
            "cid": cat_id,
            "cant": cantidad,
        },
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


@pytest.mark.asyncio
async def test_resuelve_la_cantidad_pedida_por_el_tramo(session: AsyncSession):
    """RED→GREEN: un tramo de 10 sobre un pool de 30 devuelve 10 preguntas."""
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
    sid = await _sesion(session, examen_id)

    elegidas = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    assert len(elegidas) == 10
    assert len(set(elegidas)) == 10


@pytest.mark.asyncio
async def test_el_set_queda_persistido_en_el_intento(session: AsyncSession):
    """Lo sorteado se guarda: es lo que permite reconstruir qué rindió cada alumno."""
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
    sid = await _sesion(session, examen_id)

    elegidas = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    filas = await session.execute(
        text(
            "SELECT pregunta_id::text FROM pregunta_sesion WHERE session_id = :sid"
            " ORDER BY orden"
        ),
        {"sid": sid},
    )
    assert [r[0] for r in filas.fetchall()] == elegidas


@pytest.mark.asyncio
async def test_llamarlo_de_nuevo_devuelve_el_mismo_set(session: AsyncSession):
    """Idempotente: el alumno recarga la página y sigue viendo SU examen.

    Si re-sorteara, un alumno podría refrescar hasta que le toquen preguntas
    fáciles, y las respuestas que ya cargó quedarían huérfanas.
    """
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
    sid = await _sesion(session, examen_id)

    primera = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()
    segunda = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    assert primera == segunda


@pytest.mark.asyncio
async def test_dos_alumnos_reciben_sets_distintos(session: AsyncSession):
    """TRIANGULATE: el objetivo del cambio. Con 10 de 30, dos sets iguales serían
    1 en 30 millones — si esto falla, el sorteo no es por intento."""
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
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
    assert len(de_a) == len(de_b) == 10


@pytest.mark.asyncio
async def test_sortea_del_pool_del_examen_y_no_del_banco(session: AsyncSession):
    """El blindaje: todo lo sorteado sale del pool copiado en ESTE examen.

    Es lo que hace que tocar el banco no pueda romper un examen. Moodle necesita
    versionado de preguntas para lo mismo, porque referencia el banco.
    """
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
    sid = await _sesion(session, examen_id)

    elegidas = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    del_pool = await session.execute(
        text("SELECT id::text FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": examen_id},
    )
    assert set(elegidas) <= {r[0] for r in del_pool.fetchall()}


@pytest.mark.asyncio
async def test_borrar_la_categoria_del_banco_no_rompe_el_sorteo(session: AsyncSession):
    """El caso concreto que preocupaba: alguien borra la categoría del banco.

    El tramo queda con `categoria_id` en NULL (SET NULL) pero las preguntas ya
    están copiadas, así que el alumno rinde igual.
    """
    examen_id = await _examen_con_sorteo(session, pool=30, cantidad=10)
    sid = await _sesion(session, examen_id)

    await session.execute(
        text(
            "DELETE FROM categoria_pregunta WHERE id IN"
            " (SELECT categoria_id FROM tramo_sorteo_examen WHERE examen_id = :eid)"
        ),
        {"eid": examen_id},
    )
    await session.commit()

    elegidas = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    assert len(elegidas) == 10


@pytest.mark.asyncio
async def test_pool_insuficiente_falla_fuerte(session: AsyncSession):
    """Si el pool no alcanza, se rompe con un error propio y NO se persiste nada.

    No debería llegar acá nunca: el tamaño del pool se valida al armar el examen.
    Es la red de seguridad, y prefiere fallar a servir un examen incompleto.
    """
    examen_id = await _examen_con_sorteo(session, pool=4, cantidad=10)
    sid = await _sesion(session, examen_id)

    with pytest.raises(PoolInsuficienteError):
        await resolver_preguntas_del_intento(
            db=session, session_id=sid, examen_contenido_id=examen_id
        )
    await session.rollback()

    filas = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_sesion WHERE session_id = :sid"),
        {"sid": sid},
    )
    assert filas.scalar_one() == 0


@pytest.mark.asyncio
async def test_modo_fijo_devuelve_las_seleccionadas_y_no_persiste(
    session: AsyncSession,
):
    """Compat: un examen 'fijo' se comporta EXACTAMENTE igual que antes.

    Devuelve las marcadas con seleccionada=True y no escribe en `pregunta_sesion`:
    los lectores viejos siguen resolviendo por la marca.
    """
    examen_id = await _examen_con_sorteo(session, pool=6, cantidad=3, modo="fijo")
    await session.execute(
        text(
            "UPDATE pregunta_examen SET seleccionada = true"
            " WHERE examen_id = :eid AND orden < 4"
        ),
        {"eid": examen_id},
    )
    await session.commit()
    sid = await _sesion(session, examen_id)

    elegidas = await resolver_preguntas_del_intento(
        db=session, session_id=sid, examen_contenido_id=examen_id
    )
    await session.commit()

    assert len(elegidas) == 4
    filas = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_sesion WHERE session_id = :sid"),
        {"sid": sid},
    )
    assert filas.scalar_one() == 0


@pytest.mark.asyncio
async def test_dos_pedidos_simultaneos_no_duplican_el_sorteo(factory):
    """Doble click o dos pestañas: el intento termina con UN solo set.

    Sin candado, dos sorteos concurrentes podrían insertar sets distintos y dejar
    al alumno con el doble de preguntas.
    """
    async with factory() as s:
        examen_id = await _examen_con_sorteo(s, pool=30, cantidad=10)
        sid = await _sesion(s, examen_id)

    async def resolver() -> list[str]:
        async with factory() as s:
            elegidas = await resolver_preguntas_del_intento(
                db=s, session_id=sid, examen_contenido_id=examen_id
            )
            await s.commit()
            return elegidas

    a, b = await asyncio.gather(resolver(), resolver())

    assert a == b
    async with factory() as s:
        filas = await s.execute(
            text("SELECT COUNT(*) FROM pregunta_sesion WHERE session_id = :sid"),
            {"sid": sid},
        )
        assert filas.scalar_one() == 10
