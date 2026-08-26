"""Asignación de coordinadores a cargo de una materia (c-79, N:M).

`POST /materias/{id}/coordinadores` agrega y `DELETE /materias/{id}/coordinadores/{cid}`
quita un coordinador. Gemelo de la asignación de tutores a comisión, un nivel más
arriba: el tutor va a la COMISIÓN, el coordinador a la MATERIA entera.

Por qué esto es crítico y no cosmético: hasta c-79 el coordinador tenía alcance
institucional (veía todo, igual que un admin). Ahora queda ACOTADO a las materias
que tiene asignadas — un coordinador sin materias no ve nada. Estos tests fijan ese
contrato en las dos direcciones: sin asignación no ve, con asignación ve.

Cubre además que `GET /materias` devuelva los coordinadores ya resueltos, que es lo
que consume el diálogo de asignación del panel de Materias.

DB real (DATABASE_URL). Sin mocks de DB.
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
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "inscripcion",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    InscripcionModel.__table__,
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
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
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
    # Mismo montaje que main_activeexam: `GET /materias` vive en el router de
    # rendición, no en el de catálogo. Sin este include el listado da 405.
    application.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_usuario(
    factory,
    *,
    roles: list[str],
    nombre: str | None = "Cora",
    apellido: str | None = "Díaz",
) -> str:
    legajo = f"U-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(
            username=legajo,
            email=f"{legajo.lower()}@uni.edu",
            roles=roles,
            nombre=nombre,
            apellido=apellido,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_materia(factory) -> str:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        mid = materia.id
        await s.commit()
    return mid


def _client(app, roles: list[str], *, subject: str = "test-subject"):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


def _ids(body) -> set[str]:
    return {c["id"] for c in body["coordinadores"]}


@pytest.mark.asyncio
async def test_admin_agrega_coordinador_y_viaja_el_nombre(app, factory):
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert _ids(body) == {coord_id}
    # El nombre viaja RESUELTO: la UI no tiene que pedir el usuario aparte.
    assert body["coordinadores"][0]["nombre"] == "Cora Díaz"


@pytest.mark.asyncio
async def test_una_materia_admite_varios_coordinadores(app, factory):
    """Co-coordinación: agregar un segundo NO reemplaza al primero."""
    materia_id = await _crear_materia(factory)
    coord_a = await _crear_usuario(factory, roles=["coordinador"])
    coord_b = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_a},
        )
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_b},
        )

    assert resp.status_code == 201, resp.text
    assert _ids(resp.json()) == {coord_a, coord_b}


@pytest.mark.asyncio
async def test_agregar_dos_veces_al_mismo_coordinador_es_idempotente(app, factory):
    """Reintentar (doble click, retry de red) no duplica ni falla."""
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )

    assert resp.status_code == 201, resp.text
    assert resp.json()["coordinadores"] == [{"id": coord_id, "nombre": "Cora Díaz"}]


@pytest.mark.asyncio
async def test_no_se_puede_coordinar_sin_tener_el_rol(app, factory):
    """Asignar a un tutor le daría alcance de materia entera por la puerta de atrás."""
    materia_id = await _crear_materia(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": tutor_id},
        )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "no_es_coordinador"


@pytest.mark.asyncio
async def test_tutor_no_puede_asignar_coordinadores(app, factory):
    """La capacidad `asignar_docente` no incluye al tutor."""
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["tutor"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_quitar_coordinador_deja_la_materia_sin_ese_coordinador(app, factory):
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )
        resp = await c.delete(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores/{coord_id}"
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["coordinadores"] == []


@pytest.mark.asyncio
async def test_quitar_un_coordinador_no_afecta_a_los_demas(app, factory):
    materia_id = await _crear_materia(factory)
    coord_a = await _crear_usuario(factory, roles=["coordinador"])
    coord_b = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        for cid in (coord_a, coord_b):
            await c.post(
                f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
                json={"coordinador_id": cid},
            )
        resp = await c.delete(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores/{coord_a}"
        )

    assert resp.status_code == 200, resp.text
    assert _ids(resp.json()) == {coord_b}


@pytest.mark.asyncio
async def test_materia_inexistente_404(app, factory):
    coord_id = await _crear_usuario(factory, roles=["coordinador"])
    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/materias/{uuid.uuid4()}/coordinadores",
            json={"coordinador_id": coord_id},
        )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_listado_de_materias_trae_los_coordinadores_resueltos(app, factory):
    """Lo que consume el diálogo del panel: sin esto la UI no sabe a quién mostrar."""
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )
        resp = await c.get("/api/v1/exam-content/materias")

    assert resp.status_code == 200, resp.text
    materia = next(m for m in resp.json() if m["id"] == materia_id)
    assert materia["coordinadores"] == [{"id": coord_id, "nombre": "Cora Díaz"}]


@pytest.mark.asyncio
async def test_coordinador_sin_materias_asignadas_no_ve_ninguna(app, factory):
    """El corazón de c-79: antes veía TODO el sistema, igual que un admin."""
    await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["coordinador"], subject=coord_id) as c:
        resp = await c.get("/api/v1/exam-content/materias")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_coordinador_ve_la_materia_recien_asignada(app, factory):
    """Triangulación del anterior: la asignación es lo que le abre la visibilidad."""
    materia_id = await _crear_materia(factory)
    coord_id = await _crear_usuario(factory, roles=["coordinador"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coord_id},
        )

    async with _client(app, ["coordinador"], subject=coord_id) as c:
        resp = await c.get("/api/v1/exam-content/materias")

    assert resp.status_code == 200, resp.text
    assert [m["id"] for m in resp.json()] == [materia_id]
