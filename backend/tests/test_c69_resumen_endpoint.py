"""Resumen de un examen para el encabezado del detalle (C-69 admin-sync).

NUEVO endpoint GET /api/v1/exam-content/{examen_id}/resumen:
  Devuelve { id, titulo, cantidad_preguntas, comision_id, comision_nombre,
  materia_nombre } — los metadatos del encabezado del detalle del admin.
  Reusa el read-model de resumen (LEFT JOIN materia/comisión + count preguntas).
  Cualquier principal autenticado (sin admin/MFA). 404 si no existe.
  D3: es_correcta NUNCA expuesta; tampoco viajan preguntas/opciones.

DB real (DATABASE_URL).
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

from app.domain.exam_content.entities import (
    Comision,
    ExamenContenido,
    Materia,
    OpcionRespuesta,
    Pregunta,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
    ExamenContenidoSqlRepository,
    MateriaSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido", "comision", "materia")


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
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_and_factory(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_taking_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    return app, factory


@pytest_asyncio.fixture
async def client(app_and_factory):
    app, _ = app_and_factory
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def factory(app_and_factory):
    _, fac = app_and_factory
    return fac


def _examen(titulo: str, comision_id: str | None, n_preguntas: int) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        comision_id=comision_id,
        preguntas=tuple(
            Pregunta(
                enunciado=f"P{i}",
                tipo="multichoice",
                orden=i,
                opciones=(
                    OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                ),
            )
            for i in range(n_preguntas)
        ),
    )


async def _seed_con_comision(factory, *, titulo: str, n_preguntas: int) -> tuple[str, str, str]:
    """Crea materia+comisión y un examen asociado. Devuelve (examen_id, materia_nombre, comision_nombre)."""
    tag = uuid.uuid4().hex[:8]
    materia_nombre = f"Analisis {tag}"
    comision_nombre = f"Comision {tag}"
    async with factory() as session:
        materia = await MateriaSqlRepository(session).guardar(
            Materia(codigo=f"AM-{tag}", nombre=materia_nombre)
        )
        comision = await ComisionSqlRepository(session).guardar(
            Comision(codigo=f"C1-{tag}", nombre=comision_nombre,
                     materia_id=materia.id, periodo="1C", anio=2026)
        )
        repo = ExamenContenidoSqlRepository(session)
        examen = await repo.guardar(_examen(titulo, comision.id, n_preguntas))
        await session.commit()
    return examen.id, materia_nombre, comision_nombre


async def _seed_sin_comision(factory, *, titulo: str, n_preguntas: int) -> str:
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        examen = await repo.guardar(_examen(titulo, None, n_preguntas))
        await session.commit()
    return examen.id


# ---------------------------------------------------------------------------
# Endpoint GET /{examen_id}/resumen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resumen_devuelve_metadata_con_comision(client, factory):
    examen_id, materia_nombre, comision_nombre = await _seed_con_comision(
        factory, titulo=f"Examen {uuid.uuid4().hex[:6]}", n_preguntas=2
    )
    resp = await client.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "id",
        "titulo",
        "cantidad_preguntas",
        "comision_id",
        "comision_nombre",
        "materia_nombre",
    }
    assert body["id"] == examen_id
    assert body["cantidad_preguntas"] == 2
    assert body["materia_nombre"] == materia_nombre
    assert body["comision_nombre"] == comision_nombre
    assert body["comision_id"] is not None


@pytest.mark.asyncio
async def test_resumen_sin_comision_devuelve_nulls(client, factory):
    examen_id = await _seed_sin_comision(
        factory, titulo=f"Suelto {uuid.uuid4().hex[:6]}", n_preguntas=3
    )
    resp = await client.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cantidad_preguntas"] == 3
    assert body["comision_id"] is None
    assert body["comision_nombre"] is None
    assert body["materia_nombre"] is None


@pytest.mark.asyncio
async def test_resumen_404_si_no_existe(client):
    resp = await client.get(f"/api/v1/exam-content/{uuid.uuid4()}/resumen")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_resumen_no_expone_es_correcta_ni_preguntas(client, factory):
    examen_id, _materia, _comision = await _seed_con_comision(
        factory, titulo=f"D3 {uuid.uuid4().hex[:6]}", n_preguntas=2
    )
    resp = await client.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # D3: ni opciones, ni preguntas, ni es_correcta viajan en el resumen
    assert "es_correcta" not in resp.text
    assert "preguntas" not in body
    assert "opciones" not in body


# ---------------------------------------------------------------------------
# Repo: obtener_resumen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_obtener_resumen_existente(factory):
    examen_id, materia_nombre, comision_nombre = await _seed_con_comision(
        factory, titulo=f"Repo {uuid.uuid4().hex[:6]}", n_preguntas=4
    )
    async with factory() as session:
        resumen = await ExamenContenidoSqlRepository(session).obtener_resumen(examen_id)
    assert resumen is not None
    assert resumen.id == examen_id
    assert resumen.cantidad_preguntas == 4
    assert resumen.materia_nombre == materia_nombre
    assert resumen.comision_nombre == comision_nombre


@pytest.mark.asyncio
async def test_repo_obtener_resumen_inexistente_devuelve_none(factory):
    async with factory() as session:
        resumen = await ExamenContenidoSqlRepository(session).obtener_resumen(
            str(uuid.uuid4())
        )
    assert resumen is None
