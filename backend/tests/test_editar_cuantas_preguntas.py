"""Cambiar cuántas preguntas rinde cada alumno, después de crear el examen.

Poner 10 y darse cuenta de que querías 12 no debería obligar a borrar el examen
y armarlo de nuevo. Moodle deja editar el cuestionario mientras nadie lo haya
rendido y lo bloquea apenas hay intentos; acá va la misma regla, que además es
la que ya usa "volver a borrador".

Las rendiciones de PRUEBA del docente no bloquean: para eso existen.

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
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    PreguntaExamenModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "proctoring_session",
    "tramo_sorteo_examen",
    "pregunta_examen",
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
                PreguntaExamenModel.__table__,
                TramoSorteoExamenModel.__table__,
                ProctoringSessionModel.__table__,
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


async def _examen_de_10_sobre_30(session: AsyncSession) -> str:
    """Examen que sortea 10 de un pool de 30, con un solo tramo."""
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"EDT-{mid[:8]}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :m, :c, 'Comisión', :k)"
        ),
        {"id": cid, "m": mid, "c": f"C-{cid[:6]}", "k": f"K-{cid[:6]}"},
    )
    eid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido"
            " (id, comision_id, titulo, borrador, modo_preguntas)"
            " VALUES (:id, :c, 'Parcial', true, 'sorteo_por_intento')"
        ),
        {"id": eid, "c": cid},
    )
    for i in range(30):
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden)"
                " VALUES (:id, :e, :q, 'multichoice', :o)"
            ),
            {"id": str(uuid.uuid4()), "e": eid, "q": f"P{i}", "o": i},
        )
    await session.execute(
        text(
            "INSERT INTO tramo_sorteo_examen"
            " (id, examen_id, categoria_id, incluir_subcategorias, cantidad, orden)"
            " VALUES (:id, :e, NULL, true, 10, 0)"
        ),
        {"id": str(uuid.uuid4()), "e": eid},
    )
    await session.commit()
    return eid


async def _rindio(session: AsyncSession, examen_id: str, *, es_prueba: bool) -> None:
    await session.execute(
        text(
            "INSERT INTO proctoring_session"
            " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email,"
            "  creada_en, es_prueba)"
            " VALUES (:id, :e, 'examen', 'quien-sea', 'q@test.local', :c, :p)"
        ),
        {
            "id": str(uuid.uuid4()),
            "e": examen_id,
            "c": datetime.now(timezone.utc),
            "p": es_prueba,
        },
    )
    await session.commit()


async def _cantidad(session: AsyncSession, examen_id: str) -> int:
    return (
        await session.execute(
            text("SELECT cantidad FROM tramo_sorteo_examen WHERE examen_id = :e"),
            {"e": examen_id},
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_se_puede_pasar_de_10_a_12(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen_de_10_sobre_30(session)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 0, "cantidad": 12}]},
    )

    assert resp.status_code == 200, resp.text
    assert await _cantidad(session, examen_id) == 12


@pytest.mark.asyncio
async def test_no_se_puede_pedir_mas_de_las_que_hay_en_el_pool(
    client_admin: AsyncClient, session: AsyncSession
):
    """Con 30 en el pool, pedir 31 dejaría el examen roto para el primer alumno."""
    examen_id = await _examen_de_10_sobre_30(session)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 0, "cantidad": 31}]},
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "sorteo_insuficiente"
    assert await _cantidad(session, examen_id) == 10


@pytest.mark.asyncio
async def test_con_alguien_que_ya_rindio_no_se_toca(
    client_admin: AsyncClient, session: AsyncSession
):
    """Misma regla que Moodle: con intentos, el examen deja de ser editable.

    Cambiarlo ahí haría que dos alumnos del mismo examen rindan distinta
    cantidad de preguntas, sobre la misma escala de nota.
    """
    examen_id = await _examen_de_10_sobre_30(session)
    await _rindio(session, examen_id, es_prueba=False)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 0, "cantidad": 12}]},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "examen_con_intentos"
    assert await _cantidad(session, examen_id) == 10


@pytest.mark.asyncio
async def test_una_prueba_del_docente_no_bloquea(
    client_admin: AsyncClient, session: AsyncSession
):
    """Para eso existe: probar el examen y corregirlo antes de habilitarlo."""
    examen_id = await _examen_de_10_sobre_30(session)
    await _rindio(session, examen_id, es_prueba=True)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 0, "cantidad": 12}]},
    )

    assert resp.status_code == 200, resp.text
    assert await _cantidad(session, examen_id) == 12


@pytest.mark.asyncio
async def test_cero_preguntas_no_es_un_examen(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen_de_10_sobre_30(session)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 0, "cantidad": 0}]},
    )

    assert resp.status_code == 422, resp.text
    assert await _cantidad(session, examen_id) == 10


@pytest.mark.asyncio
async def test_un_tramo_que_no_existe_no_crea_nada(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen_de_10_sobre_30(session)

    resp = await client_admin.patch(
        f"/api/v1/exam-content/{examen_id}/sorteo",
        json={"tramos": [{"orden": 7, "cantidad": 5}]},
    )

    assert resp.status_code == 404, resp.text
    assert await _cantidad(session, examen_id) == 10
