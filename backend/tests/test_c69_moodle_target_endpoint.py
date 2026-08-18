"""Destino de write-back a Moodle POR EXAMEN (C-69, D12 parte B).

Endpoints (admin-only, SIN MFA — guard a nivel router, igual que el import):
- POST /api/v1/exam-content/{examen_id}/moodle-target  → fija courseid/cmid.
- GET  /api/v1/exam-content/{examen_id}/moodle-target  → lee el destino actual.

Valores AUTORITATIVOS; null limpia y cae al fallback global. 404 si el examen
no existe. DB real (DATABASE_URL). NO expone es_correcta.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = ["opcion_respuesta", "pregunta_examen", "examen_contenido"]
_TABLES_TO_CREATE = [
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
]


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
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"]),
    )


async def _crear_examen(factory) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=f"Parcial {uuid.uuid4().hex[:6]}")
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


@pytest.mark.asyncio
async def test_set_moodle_target_200(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 909, "moodle_cmid": 17},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "examen_id": examen_id,
        "moodle_courseid": 909,
        "moodle_cmid": 17,
    }

    # persistido en la DB
    async with factory() as s:
        row = (
            await s.execute(
                select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one()
        assert row.moodle_courseid == 909
        assert row.moodle_cmid == 17


@pytest.mark.asyncio
async def test_get_moodle_target_lee_lo_seteado(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 5, "moodle_cmid": 6},
        )
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/moodle-target")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "examen_id": examen_id,
        "moodle_courseid": 5,
        "moodle_cmid": 6,
    }


@pytest.mark.asyncio
async def test_set_moodle_target_null_limpia(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 1, "moodle_cmid": 2},
        )
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": None, "moodle_cmid": None},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["moodle_courseid"] is None
    assert resp.json()["moodle_cmid"] is None


@pytest.mark.asyncio
async def test_set_moodle_target_examen_inexistente_404(app):
    async with _admin_client(app) as c:
        resp = await c.post(
            "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/moodle-target",
            json={"moodle_courseid": 1, "moodle_cmid": 1},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_moodle_target_extra_forbid_422(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 1, "moodle_cmid": 1, "campo_extra": "x"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_moodle_target_admin_only(app, factory):
    examen_id = await _crear_examen(factory)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 1, "moodle_cmid": 1},
        )
    assert resp.status_code == 403
