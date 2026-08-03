"""Paginación + búsqueda serverside del catálogo de exámenes (C-69 admin-sync, tarea 4).

NUEVO contrato de GET /api/v1/exam-content:
  Devuelve forma paginada { items: [...], total, page, page_size }.
  Query params: q (título/materia/comisión), page (1..), page_size.
  Default page_size amplio (1000) → sin params, devuelve todo (compat frontend).
  Filtrado/orden SIEMPRE en SQL (serverside).

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
# El gate de inscripción (C-71) que aplica el listado consulta inscripcion+usuario:
# sin esas tablas el endpoint revienta con UndefinedTable.
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
    ExamenContenidoSqlRepository,
    MateriaSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = (
    "inscripcion",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
    "usuario",
)


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
                UsuarioModel.__table__,
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                InscripcionModel.__table__,
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
        # Rol de gestión: estos tests verifican la FORMA de la paginación y el
        # filtro server-side del catálogo, no el gate de inscripción (C-71). Con
        # rol 'estudiante' el gate filtra a las comisiones inscriptas y el total
        # daría 0, que es el comportamiento correcto pero no lo que se prueba acá.
        headers=auth_headers(["admin_examenes"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def factory(app_and_factory):
    _, fac = app_and_factory
    return fac


def _examen(titulo: str, comision_id: str | None) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        comision_id=comision_id,
        preguntas=(
            Pregunta(
                enunciado="P",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                ),
            ),
        ),
    )


async def _seed(factory, titulos_con_materia: list[tuple[str, str | None]]) -> str:
    """Crea una materia+comisión y los exámenes. Devuelve el tag único usado."""
    tag = uuid.uuid4().hex[:8]
    async with factory() as session:
        materia = await MateriaSqlRepository(session).guardar(
            Materia(codigo=f"FIS-{tag}", nombre=f"Fisica {tag}")
        )
        comision = await ComisionSqlRepository(session).guardar(
            Comision(codigo=f"C1-{tag}", nombre=f"ComisionAlfa {tag}",
                     materia_id=materia.id, periodo="1C", anio=2026,
                     codigo_matriculacion=f"FIS-{tag}-C1")
        )
        repo = ExamenContenidoSqlRepository(session)
        for titulo, _materia_marker in titulos_con_materia:
            await repo.guardar(_examen(titulo, comision.id))
        await session.commit()
    return tag


# ---------------------------------------------------------------------------
# Forma paginada
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listado_devuelve_forma_paginada(client, factory):
    tag = await _seed(factory, [(f"Alfa {uuid.uuid4().hex[:6]}", None)])
    resp = await client.get("/api/v1/exam-content")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["page_size"] >= 100  # default amplio (compat)
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_page_size_limita_items_pero_total_es_global(client, factory):
    tag = await _seed(
        factory,
        [(f"PG-{uuid.uuid4().hex[:6]} {i}", None) for i in range(5)],
    )
    # filtra por el tag de materia ("Fisica {tag}") para aislar del set global
    resp = await client.get(f"/api/v1/exam-content?q={tag}&page=1&page_size=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page_size"] == 2

    resp3 = await client.get(f"/api/v1/exam-content?q={tag}&page=3&page_size=2")
    body3 = resp3.json()
    assert len(body3["items"]) == 1  # 5 = 2 + 2 + 1


@pytest.mark.asyncio
async def test_q_filtra_por_titulo_serverside(client, factory):
    unico = "ZZQUIM" + uuid.uuid4().hex[:6]
    tag = await _seed(factory, [(f"Quimica {unico}", None), (f"Otro {uuid.uuid4().hex[:6]}", None)])
    resp = await client.get(f"/api/v1/exam-content?q={unico}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["titulo"] == f"Quimica {unico}"
    # D3 invariante
    assert "es_correcta" not in body["items"][0]


@pytest.mark.asyncio
async def test_q_filtra_por_materia_y_comision(client, factory):
    tag = await _seed(factory, [(f"Examen {uuid.uuid4().hex[:6]}", None)])
    # la materia se llama "Fisica {tag}" y la comisión "ComisionAlfa {tag}"
    por_materia = await client.get(f"/api/v1/exam-content?q=Fisica {tag}")
    assert por_materia.status_code == 200
    assert por_materia.json()["total"] >= 1

    por_comision = await client.get(f"/api/v1/exam-content?q=ComisionAlfa {tag}")
    assert por_comision.status_code == 200
    assert por_comision.json()["total"] >= 1
