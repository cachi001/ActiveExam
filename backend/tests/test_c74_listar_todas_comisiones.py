"""C-74: GET /exam-content/comisiones — todas las comisiones con su materia embebida.

Selector combinado único ("CÓDIGO - Materia") para reemplazar el patrón de
dos selects encadenados (Materia → Comisión).

DB real (regla dura #4).
"""

from __future__ import annotations

import os
import uuid

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
    MateriaModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = ["comision", "materia"]


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
            tables=[MateriaModel.__table__, ComisionModel.__table__],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_admin(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_taking_router(session_factory=factory)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _seed(session: AsyncSession) -> str:
    """Crea 2 materias (una con 2 comisiones, otra con 1) con nombres únicos
    por corrida — la tabla no se limpia entre tests del módulo. Devuelve un
    sufijo único para filtrar los resultados propios de cada test."""
    sufijo = uuid.uuid4().hex[:8]
    m1 = str(uuid.uuid4())
    m2 = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": m1, "c": f"PROG1-{sufijo}", "n": f"Programación 1 {sufijo}"},
    )
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": m2, "c": f"PROG2-{sufijo}", "n": f"Programación 2 {sufijo}"},
    )
    for mid, codigo, nombre in [
        (m1, "C1", "Comisión 1"),
        (m1, "C2", "Comisión 2"),
        (m2, "C1", "Comisión 1"),
    ]:
        await session.execute(
            text(
                "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion) "
                "VALUES (:id, :mid, :codigo, :nombre, :matr)"
            ),
            {
                "id": str(uuid.uuid4()),
                "mid": mid,
                "codigo": codigo,
                "nombre": nombre,
                "matr": f"{codigo}-{uuid.uuid4().hex[:6]}",
            },
        )
    await session.commit()
    return sufijo


@pytest.mark.asyncio
async def test_repo_listar_todas_con_materia(session: AsyncSession):
    sufijo = await _seed(session)
    repo = ComisionSqlRepository(session)

    filas = await repo.listar_todas_con_materia()
    propias = [f for f in filas if sufijo in f[1]]

    assert len(propias) == 3
    materias_nombres = {materia_nombre for _c, materia_nombre, _mc in propias}
    assert materias_nombres == {f"Programación 1 {sufijo}", f"Programación 2 {sufijo}"}


@pytest.mark.asyncio
async def test_endpoint_devuelve_materia_embebida(client_admin: AsyncClient, session: AsyncSession):
    sufijo = await _seed(session)

    resp = await client_admin.get("/api/v1/exam-content/comisiones")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    propias = [d for d in data if sufijo in d["materia_nombre"]]
    assert len(propias) == 3
    primero = propias[0]
    assert "materia_nombre" in primero
    assert "materia_codigo" in primero
    assert primero["codigo"] and primero["nombre"]
