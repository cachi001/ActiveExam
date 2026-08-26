"""Asignación de tutores a cargo de una comisión (C-73 §9.2 y §9.5, N:M desde c-79).

`POST /comisiones/{id}/tutores` agrega y `DELETE /comisiones/{id}/tutores/{tutor_id}`
quita un tutor a cargo. Reemplazan al viejo `PUT /comisiones/{id}/docente`, que solo
permitía UN tutor por comisión (c-79: co-dictado, cobertura de licencias).

Es el dato del que se DERIVA quién devuelve la nota a Moodle y qué exámenes puede
tocar ese tutor, así que:

- la capacidad `asignar_docente` NO la tiene el rol TUTOR (no se autoasigna),
- el usuario asignado debe existir, estar activo y tener rol tutor,
- el listado devuelve los tutores con el nombre YA resuelto.

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
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
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
    return application


async def _crear_usuario(
    factory, *, roles: list[str], nombre: str | None = "Ana", apellido: str | None = "Gómez"
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


async def _crear_materia_y_comision(factory) -> tuple[str, str]:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        ids = (materia.id, comision.id)
        await s.commit()
    return ids


def _client(app, roles: list[str]):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles),
    )


def _ids(body) -> set[str]:
    return {t["id"] for t in body["tutores"]}


@pytest.mark.asyncio
async def test_admin_agrega_tutor_y_viaja_el_nombre(app, factory):
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert _ids(body) == {tutor_id}
    # El nombre viaja RESUELTO: la UI no tiene que pedir el usuario aparte.
    assert body["tutores"][0]["nombre"] == "Ana Gómez"


@pytest.mark.asyncio
async def test_una_comision_admite_varios_tutores(app, factory):
    """c-79 — el cambio central: co-dictado. Agregar un segundo tutor NO reemplaza
    al primero (con el modelo 1:1 anterior, el segundo pisaba al primero)."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_a = await _crear_usuario(factory, roles=["tutor"])
    tutor_b = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_a},
        )
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_b},
        )

    assert resp.status_code == 201, resp.text
    assert _ids(resp.json()) == {tutor_a, tutor_b}


@pytest.mark.asyncio
async def test_agregar_dos_veces_al_mismo_tutor_es_idempotente(app, factory):
    """Reintentar (doble click, retry de red) no duplica ni falla."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tutores"] == [
        t for t in resp.json()["tutores"] if t["id"] == tutor_id
    ]
    assert len(resp.json()["tutores"]) == 1


@pytest.mark.asyncio
async def test_tutor_no_puede_asignarse_a_si_mismo(app, factory):
    """El control de pertenencia no sirve si el controlado puede auto-otorgárselo."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["tutor"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_no_se_puede_poner_a_cargo_a_quien_no_es_tutor(app, factory):
    """Un alumno a cargo devolvería la nota con una identidad equivocada."""
    _, comision_id = await _crear_materia_y_comision(factory)
    alumno_id = await _crear_usuario(factory, roles=["estudiante"])

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": alumno_id},
        )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "no_es_tutor"


@pytest.mark.asyncio
async def test_quitar_tutor_deja_la_comision_sin_ese_tutor(app, factory):
    """Una comisión puede quedar sin tutores: no es un error, degrada a institucional."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )
        resp = await c.delete(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores/{tutor_id}"
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["tutores"] == []


@pytest.mark.asyncio
async def test_quitar_un_tutor_no_afecta_a_los_demas(app, factory):
    """Triangulación del co-dictado: sacar a uno deja al otro a cargo."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_a = await _crear_usuario(factory, roles=["tutor"])
    tutor_b = await _crear_usuario(factory, roles=["tutor"])

    async with _client(app, ["admin_sistema"]) as c:
        for t in (tutor_a, tutor_b):
            await c.post(
                f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
                json={"tutor_id": t},
            )
        resp = await c.delete(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores/{tutor_a}"
        )

    assert resp.status_code == 200, resp.text
    assert _ids(resp.json()) == {tutor_b}


@pytest.mark.asyncio
async def test_comision_inexistente_404(app, factory):
    tutor_id = await _crear_usuario(factory, roles=["tutor"])
    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{uuid.uuid4()}/tutores",
            json={"tutor_id": tutor_id},
        )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_usuario_dado_de_baja_no_puede_quedar_a_cargo(app, factory):
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"])
    async with factory() as s:
        await s.execute(
            text("UPDATE usuario SET eliminado_en = now() WHERE id = :i"),
            {"i": tutor_id},
        )
        await s.commit()

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "docente_invalido"


@pytest.mark.asyncio
async def test_nombre_cae_al_legajo_si_el_usuario_no_tiene_nombre(app, factory):
    """Usuarios federados/seed viejos pueden no tener nombre: mostrar un UUID no sirve."""
    _, comision_id = await _crear_materia_y_comision(factory)
    tutor_id = await _crear_usuario(factory, roles=["tutor"], nombre=None, apellido=None)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": tutor_id},
        )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tutores"][0]["nombre"].startswith("U-")
