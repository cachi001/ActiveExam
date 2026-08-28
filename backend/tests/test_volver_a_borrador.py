"""Deshabilitar un examen: volver a borrador mientras nadie lo haya rendido.

Habilitar era un camino de ida, y eso convertía un error de un click en algo
irreversible: el examen quedaba visible para los alumnos y la única salida era
darlo de baja. Volver atrás es seguro exactamente hasta que alguien empieza a
rendirlo; a partir de ahí, esconderlo le sacaría el examen de abajo a quien está
en el medio, así que el endpoint tiene que negarse.

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
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "proctoring_session",
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


async def _examen(session: AsyncSession, *, borrador: bool) -> str:
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"BOR-{mid[:8]}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision"
            " (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :m, :c, 'Comisión', :k)"
        ),
        {"id": cid, "m": mid, "c": f"C-{cid[:6]}", "k": f"K-{cid[:6]}"},
    )
    eid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido (id, comision_id, titulo, borrador)"
            " VALUES (:id, :c, :t, :b)"
        ),
        {"id": eid, "c": cid, "t": f"Examen {eid[:8]}", "b": borrador},
    )
    await session.commit()
    return eid


async def _borrador_de(session: AsyncSession, examen_id: str) -> bool:
    return (
        await session.execute(
            text("SELECT borrador FROM examen_contenido WHERE id = :id"),
            {"id": examen_id},
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_un_examen_sin_intentos_puede_volver_a_borrador(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen(session, borrador=False)

    resp = await client_admin.post(f"/api/v1/exam-content/{examen_id}/volver-a-borrador")

    assert resp.status_code == 204, resp.text
    assert await _borrador_de(session, examen_id) is True


@pytest.mark.asyncio
async def test_con_alguien_rindiendo_no_se_puede_esconder(
    client_admin: AsyncClient, session: AsyncSession
):
    """El caso que hace que esto no sea un simple toggle."""
    examen_id = await _examen(session, borrador=False)
    await session.execute(
        text(
            "INSERT INTO proctoring_session"
            " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email, creada_en)"
            " VALUES (:id, :e, 'examen', 'a-1', 'a1@test.local', :c)"
        ),
        {
            "id": str(uuid.uuid4()),
            "e": examen_id,
            "c": datetime.now(timezone.utc),
        },
    )
    await session.commit()

    resp = await client_admin.post(f"/api/v1/exam-content/{examen_id}/volver-a-borrador")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "examen_con_intentos"
    # Y no lo escondió a medias.
    assert await _borrador_de(session, examen_id) is False


@pytest.mark.asyncio
async def test_el_mensaje_dice_cuantos_rindieron(
    client_admin: AsyncClient, session: AsyncSession
):
    """Sin el número, el docente no sabe si son 2 alumnos o el curso entero."""
    examen_id = await _examen(session, borrador=False)
    for i in range(3):
        await session.execute(
            text(
                "INSERT INTO proctoring_session"
                " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email, creada_en)"
                " VALUES (:id, :e, 'examen', :n, :m, :c)"
            ),
            {
                "id": str(uuid.uuid4()),
                "e": examen_id,
                "n": f"a-{i}",
                "m": f"a{i}@test.local",
                "c": datetime.now(timezone.utc),
            },
        )
    await session.commit()

    resp = await client_admin.post(f"/api/v1/exam-content/{examen_id}/volver-a-borrador")

    assert resp.status_code == 409
    assert resp.json()["detail"]["intentos"] == 3


@pytest.mark.asyncio
async def test_uno_que_ya_estaba_en_borrador_da_404(
    client_admin: AsyncClient, session: AsyncSession
):
    """Nada que deshacer: 404, igual que habilitar uno ya habilitado."""
    examen_id = await _examen(session, borrador=True)

    resp = await client_admin.post(f"/api/v1/exam-content/{examen_id}/volver-a-borrador")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_queda_auditado_quien_lo_escondio(
    client_admin: AsyncClient, session: AsyncSession
):
    """Cambia si el examen se puede rendir: tiene que dejar rastro."""
    examen_id = await _examen(session, borrador=False)

    resp = await client_admin.post(f"/api/v1/exam-content/{examen_id}/volver-a-borrador")
    assert resp.status_code == 204

    filas = await session.execute(
        text(
            'SELECT accion FROM audit_log WHERE entidad_id = :id'
            ' ORDER BY "timestamp" DESC'
        ),
        {"id": examen_id},
    )
    assert "examen.volver_a_borrador" in [f[0] for f in filas.all()]
