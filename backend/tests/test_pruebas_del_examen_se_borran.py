"""Ver y borrar las rendiciones de prueba de un examen.

Decisión del dueño (28/8/2026): las pruebas se guardan —para poder revisar qué
se contestó y cómo se corrigió, que es para lo que sirve probar— pero se tienen
que poder eliminar. Sin eso, ensayar el examen tres veces deja tres sesiones
para siempre.

Lo que NO se puede borrar por acá es una rendición real: eso es evidencia
académica (cadena de custodia, reglas duras #6 y #7).

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


def _cliente(db_engine, roles: list[str]) -> AsyncClient:
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, mfa=True),
    )


@pytest_asyncio.fixture
async def client_admin(db_engine):
    async with _cliente(db_engine, ["admin_sistema"]) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _examen(session: AsyncSession) -> str:
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"PRB-{mid[:8]}"},
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
            "INSERT INTO examen_contenido (id, comision_id, titulo, borrador)"
            " VALUES (:id, :c, 'Parcial', true)"
        ),
        {"id": eid, "c": cid},
    )
    await session.commit()
    return eid


async def _sesion(
    session: AsyncSession, examen_id: str, *, quien: str, es_prueba: bool
) -> str:
    sid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO proctoring_session"
            " (id, examen_contenido_id, modo, alumno_idnumber, alumno_email,"
            "  creada_en, es_prueba)"
            " VALUES (:id, :e, 'examen', :n, :m, :c, :p)"
        ),
        {
            "id": sid,
            "e": examen_id,
            "n": quien,
            "m": f"{quien}@test.local",
            "c": datetime.now(timezone.utc),
            "p": es_prueba,
        },
    )
    await session.commit()
    return sid


@pytest.mark.asyncio
async def test_lista_las_pruebas_del_examen(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen(session)
    prueba = await _sesion(session, examen_id, quien="profe-1", es_prueba=True)
    await _sesion(session, examen_id, quien="alumno-1", es_prueba=False)

    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}/pruebas")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert [p["session_id"] for p in cuerpo["pruebas"]] == [prueba]


@pytest.mark.asyncio
async def test_dice_quien_y_cuando_probo(
    client_admin: AsyncClient, session: AsyncSession
):
    """Con varios docentes en la materia, "una prueba" a secas no dice nada."""
    examen_id = await _examen(session)
    await _sesion(session, examen_id, quien="profe-1", es_prueba=True)

    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}/pruebas")

    fila = resp.json()["pruebas"][0]
    assert fila["quien"] == "profe-1"
    assert fila["creada_en"] is not None


@pytest.mark.asyncio
async def test_borrar_una_prueba_la_saca(
    client_admin: AsyncClient, session: AsyncSession
):
    examen_id = await _examen(session)
    prueba = await _sesion(session, examen_id, quien="profe-1", es_prueba=True)

    resp = await client_admin.delete(
        f"/api/v1/exam-content/{examen_id}/pruebas/{prueba}"
    )

    assert resp.status_code == 204, resp.text
    quedan = await session.execute(
        text("SELECT COUNT(*) FROM proctoring_session WHERE id = :id"), {"id": prueba}
    )
    assert quedan.scalar_one() == 0


@pytest.mark.asyncio
async def test_no_se_puede_borrar_una_rendicion_real(
    client_admin: AsyncClient, session: AsyncSession
):
    """Es evidencia académica: no se borra ni aunque la pidan por este camino."""
    examen_id = await _examen(session)
    real = await _sesion(session, examen_id, quien="alumno-1", es_prueba=False)

    resp = await client_admin.delete(f"/api/v1/exam-content/{examen_id}/pruebas/{real}")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "no_es_una_prueba"
    quedan = await session.execute(
        text("SELECT COUNT(*) FROM proctoring_session WHERE id = :id"), {"id": real}
    )
    assert quedan.scalar_one() == 1


@pytest.mark.asyncio
async def test_una_prueba_de_otro_examen_no_se_borra_desde_este(
    client_admin: AsyncClient, session: AsyncSession
):
    """El id del examen en la URL tiene que acotar de verdad, no ser decorativo."""
    examen_id = await _examen(session)
    otro = await _examen(session)
    ajena = await _sesion(session, otro, quien="profe-2", es_prueba=True)

    resp = await client_admin.delete(f"/api/v1/exam-content/{examen_id}/pruebas/{ajena}")

    assert resp.status_code == 404, resp.text
