"""Rearmar el sorteo de un examen: sacar una categoría, sumar otra, cambiar cuánto.

Editar solo la cantidad no alcanza. En Moodle se puede sacar una pregunta
aleatoria del cuestionario y poner otra de otra categoría; acá, hasta ahora, la
composición quedaba congelada al crear y la única salida era borrar el examen.

`PUT /{examen_id}/sorteo` reemplaza los tramos Y el pool copiado, con el mismo
armado que usa la creación. Misma regla que el resto: se puede mientras nadie lo
haya rendido.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    BlankBancoModel,
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionBlankBancoModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "proctoring_session",
    "tramo_sorteo_examen",
    "opcion_blank_banco",
    "blank_banco",
    "opcion_banco",
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "pregunta_banco",
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
                PreguntaBancoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                OpcionBancoModel.__table__,
                BlankBancoModel.__table__,
                OpcionBlankBancoModel.__table__,
                PreguntaClozeBlankModel.__table__,
                ProctoringSessionModel.__table__,
                TramoSorteoExamenModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def client_admin(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _banco_dos_unidades(session: AsyncSession) -> tuple[str, str, str, str]:
    """Materia con U1 y U2, 5 preguntas cada una. Devuelve (materia, comision, u1, u2)."""
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"SRT-{mid[:8]}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :m, :c, 'Comisión', :k)"
        ),
        {"id": cid, "m": mid, "c": f"C-{cid[:6]}", "k": f"K-{cid[:6]}"},
    )
    cats = []
    for nombre in ("Unidad 1", "Unidad 2"):
        cat = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
                " VALUES (:id, :m, :n)"
            ),
            {"id": cat, "m": mid, "n": nombre},
        )
        for i in range(5):
            await session.execute(
                text(
                    "INSERT INTO pregunta_banco"
                    " (id, materia_id, enunciado, tipo, categoria_id)"
                    " VALUES (:id, :m, :e, 'multichoice', :c)"
                ),
                {"id": str(uuid.uuid4()), "m": mid, "e": f"{nombre}-{i}", "c": cat},
            )
        cats.append(cat)
    await session.commit()
    return mid, cid, cats[0], cats[1]


async def _crear(client: AsyncClient, materia_id: str, comision_id: str, tramos) -> str:
    resp = await client.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": f"Parcial {uuid.uuid4().hex[:6]}",
            "materia_id": materia_id,
            "comision_ids": [comision_id],
            "sorteo": tramos,
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["examen_id"]


async def _categorias_del_pool(session: AsyncSession, examen_id: str) -> set[str]:
    filas = await session.execute(
        text(
            "SELECT DISTINCT categoria_id::text FROM pregunta_examen"
            " WHERE examen_id = :e"
        ),
        {"e": examen_id},
    )
    return {f[0] for f in filas.all()}


@pytest.mark.asyncio
async def test_sacar_una_categoria_la_saca_del_pool(
    client_admin: AsyncClient, session: AsyncSession
):
    """Lo que hoy obligaba a borrar el examen y armarlo de nuevo."""
    materia_id, comision_id, u1, u2 = await _banco_dos_unidades(session)
    examen_id = await _crear(
        client_admin,
        materia_id,
        comision_id,
        [
            {"categoria_id": u1, "cantidad": 2},
            {"categoria_id": u2, "cantidad": 2},
        ],
    )
    assert await _categorias_del_pool(session, examen_id) == {u1, u2}

    resp = await client_admin.put(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"sorteo": [{"categoria_id": u1, "cantidad": 3}]},
    )

    assert resp.status_code == 200, resp.text
    assert await _categorias_del_pool(session, examen_id) == {u1}


@pytest.mark.asyncio
async def test_sumar_una_categoria_que_no_estaba(
    client_admin: AsyncClient, session: AsyncSession
):
    materia_id, comision_id, u1, u2 = await _banco_dos_unidades(session)
    examen_id = await _crear(
        client_admin, materia_id, comision_id, [{"categoria_id": u1, "cantidad": 2}]
    )

    resp = await client_admin.put(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={
            "sorteo": [
                {"categoria_id": u1, "cantidad": 2},
                {"categoria_id": u2, "cantidad": 3},
            ]
        },
    )

    assert resp.status_code == 200, resp.text
    assert await _categorias_del_pool(session, examen_id) == {u1, u2}
    assert resp.json()["largo_del_examen"] == 5


@pytest.mark.asyncio
async def test_no_quedan_los_tramos_viejos_dando_vueltas(
    client_admin: AsyncClient, session: AsyncSession
):
    """Reemplazar es reemplazar: si quedara el tramo viejo, el alumno rendiría
    preguntas de una categoría que el docente sacó."""
    materia_id, comision_id, u1, u2 = await _banco_dos_unidades(session)
    examen_id = await _crear(
        client_admin,
        materia_id,
        comision_id,
        [{"categoria_id": u1, "cantidad": 2}, {"categoria_id": u2, "cantidad": 2}],
    )

    await client_admin.put(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"sorteo": [{"categoria_id": u1, "cantidad": 3}]},
    )

    filas = await session.execute(
        text(
            "SELECT categoria_id::text, cantidad FROM tramo_sorteo_examen"
            " WHERE examen_id = :e"
        ),
        {"e": examen_id},
    )
    assert [(c, n) for c, n in filas.all()] == [(u1, 3)]


@pytest.mark.asyncio
async def test_pedir_mas_de_las_que_hay_no_deja_el_examen_a_medias(
    client_admin: AsyncClient, session: AsyncSession
):
    """Si fallara a mitad de camino, el examen quedaría sin pool y sin tramos."""
    materia_id, comision_id, u1, u2 = await _banco_dos_unidades(session)
    examen_id = await _crear(
        client_admin, materia_id, comision_id, [{"categoria_id": u1, "cantidad": 2}]
    )

    resp = await client_admin.put(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"sorteo": [{"categoria_id": u1, "cantidad": 99}]},
    )

    assert resp.status_code == 422, resp.text
    assert await _categorias_del_pool(session, examen_id) == {u1}
    filas = await session.execute(
        text("SELECT cantidad FROM tramo_sorteo_examen WHERE examen_id = :e"),
        {"e": examen_id},
    )
    assert filas.scalar_one() == 2


@pytest.mark.asyncio
async def test_con_alguien_que_ya_rindio_no_se_rearma(
    client_admin: AsyncClient, session: AsyncSession
):
    materia_id, comision_id, u1, u2 = await _banco_dos_unidades(session)
    examen_id = await _crear(
        client_admin, materia_id, comision_id, [{"categoria_id": u1, "cantidad": 2}]
    )
    await session.execute(
        text(
            "INSERT INTO proctoring_session"
            " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email, creada_en)"
            " VALUES (:id, :e, 'examen', 'a-1', 'a1@test.local', :c)"
        ),
        {"id": str(uuid.uuid4()), "e": examen_id, "c": datetime.now(timezone.utc)},
    )
    await session.commit()

    resp = await client_admin.put(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"sorteo": [{"categoria_id": u2, "cantidad": 2}]},
    )

    assert resp.status_code == 409, resp.text
    assert await _categorias_del_pool(session, examen_id) == {u1}
