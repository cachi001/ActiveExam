"""Una pregunta rota en la base no puede dejar el examen entero inabrible (27/8/2026).

EL SÍNTOMA: abrir el detalle de un examen devolvía 500 y la pantalla quedaba sin
configuración, sin destino de nota y sin poder publicar. El error era
`PreguntaInvalidaError: multichoice requiere >= 2 opciones; tiene 0`.

LA CAUSA: `GET /{id}/config` y `GET /{id}/moodle-target` llamaban a
`repo.obtener()`, que trae el examen CON todas sus preguntas y opciones y las
convierte a entidades de dominio. Esa conversión valida cada pregunta. Ninguno de
los dos endpoints usa las preguntas: `config` devuelve catorce campos escalares y
`moodle-target` devuelve dos enteros. Se pagaba la carga entera del agregado, y
con ella su validación, para leer un puñado de columnas.

O sea que una sola fila mal guardada volvía inoperable todo el examen, incluido
justamente lo que hace falta para arreglarlo.

La invariante del dominio NO se toca: una multichoice sin opciones sigue siendo
inválida, porque no se puede responder ni calificar. Lo que cambia es que leer la
configuración deje de construir preguntas que no necesita.

DB real (regla dura del proyecto: sin mocks de base).
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
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "proctoring_session",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
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
async def admin_app(factory):
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


async def _examen_con_pregunta_rota(factory) -> str:
    """Un examen con una multichoice SIN opciones, como la que dejó el import.

    Se inserta por el modelo y no por el repositorio a propósito: el repositorio
    valida, y lo que reproduce el bug es la fila ya guardada.
    """
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=f"Con rota {uuid.uuid4().hex[:6]}")
        s.add(examen)
        await s.flush()
        s.add(
            PreguntaExamenModel(
                examen_id=examen.id,
                enunciado="Multichoice a la que nunca le cargaron opciones",
                tipo="multichoice",
                orden=0,
            )
        )
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


@pytest.mark.asyncio
async def test_config_se_lee_aunque_una_pregunta_este_rota(admin_app, factory):
    examen_id = await _examen_con_pregunta_rota(factory)
    async with _admin_client(admin_app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert r.status_code == 200, (
        "Una pregunta inválida dejaba el examen entero inabrible: sin config, sin "
        f"destino de nota y sin poder publicar. Respuesta: {r.text}"
    )
    # Y devuelve la config de verdad, no un objeto vacío que disimule el problema.
    assert "nota_maxima" in r.json()


@pytest.mark.asyncio
async def test_destino_de_nota_se_lee_aunque_una_pregunta_este_rota(admin_app, factory):
    examen_id = await _examen_con_pregunta_rota(factory)
    async with _admin_client(admin_app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/moodle-target")
    assert r.status_code == 200, (
        "Sin este endpoint no se puede cargar el curso y la actividad, que es "
        f"justamente lo que hace falta para que las notas lleguen. Respuesta: {r.text}"
    )
    assert r.json()["examen_id"] == examen_id


@pytest.mark.asyncio
async def test_examen_inexistente_sigue_dando_404(admin_app, factory):
    """La tolerancia no puede convertir un 404 en un 200 vacío."""
    async with _admin_client(admin_app) as c:
        r = await c.get(f"/api/v1/exam-content/{uuid.uuid4()}/config")
    assert r.status_code == 404
