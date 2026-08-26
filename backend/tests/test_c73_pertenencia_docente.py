"""Pertenencia del DOCENTE sobre el examen (C-73 §9).

El rol DOCENTE administra "lo suyo" (ver el comentario de ``Rol.DOCENTE`` en
``roles.py``). Hasta C-73 esa regla estaba ESCRITA pero NO se aplicaba: los guards
del router de contenido son por CAPACIDAD (``gestionar_academico``), y no habia
contra que validar la propiedad porque ``comision`` no tenia docente.

Consecuencia real que estos tests cierran: un docente podia fijar el destino Moodle
del examen de OTRA comision y mandar esa nota a la libreta de una materia ajena.

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
    MateriaProfesorModel,
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
    "materia_profesor",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    # c-78: fijar el destino Moodle pasó a exigir `crear_examenes`, que el TUTOR
    # ya no tiene (E-03). El actor suma el rol PROFESOR y su membresía de
    # materia para que lo que se siga verificando sea la PERTENENCIA.
    MateriaProfesorModel.__table__,
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
        # `usuario` la crea el esquema de la app (migraciones): acá solo se asegura
        # que exista, porque comision_tutor/materia_profesor la referencian por FK.
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


async def _crear_docente(factory, legajo: str) -> str:
    """Crea un usuario con rol docente y devuelve su id (= claim ``sub``)."""
    async with factory() as s:
        u = UsuarioModel(
            username=legajo,
            email=f"{legajo.lower()}@uni.edu",
            nombre="Docente",
            apellido=legajo,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_examen_de_comision(factory, docente_id: str | None) -> str:
    """Materia + comisión (con el docente dado) + examen asociado. Devuelve examen_id."""
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
        # c-78 (migración 0093): `comision.docente_id` se dropeó. La pertenencia
        # vive SOLO en comision_tutor (N:M).
        if docente_id:
            s.add(ComisionTutorModel(comision_id=comision.id, tutor_id=docente_id))
            s.add(
                MateriaProfesorModel(materia_id=materia.id, profesor_id=docente_id)
            )
        examen = ExamenContenidoModel(
            titulo=f"Parcial {sufijo}", comision_id=comision.id
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


def _client(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_fijar_destino_moodle(app, factory):
    """RED: hoy devuelve 200. Un docente NO puede tocar el examen de otra comisión."""
    dueno = await _crear_docente(factory, f"DOC-A-{uuid.uuid4().hex[:4]}")
    ajeno = await _crear_docente(factory, f"DOC-B-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    # c-78: el rol PROFESOR es el que tiene `crear_examenes`. Se lo damos a AMBOS
    # actores para que el 403 de abajo siga siendo por PERTENENCIA (materia ajena)
    # y no por capacidad — que probaría otra cosa.
    async with _client(app, ["tutor", "profesor"], subject=ajeno) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 999, "moodle_cmid": 888},
        )

    assert resp.status_code == 403, (
        "Un docente de OTRA comisión pudo redirigir la nota a la libreta que quiso. "
        f"Respuesta: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_fijar_destino_moodle(app, factory):
    """Triangulación: el docente de la comisión del examen SÍ puede."""
    dueno = await _crear_docente(factory, f"DOC-C-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    async with _client(app, ["tutor", "profesor"], subject=dueno) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 12, "moodle_cmid": 34},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["moodle_courseid"] == 12


@pytest.mark.asyncio
async def test_admin_no_esta_limitado_por_pertenencia(app, factory):
    """Triangulación: los roles de alcance institucional operan cualquier examen."""
    dueno = await _crear_docente(factory, f"DOC-D-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    async with _client(app, ["admin_sistema"], subject="otro-sujeto") as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 77, "moodle_cmid": 88},
        )

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_examen_sin_docente_no_lo_reclama_un_docente(app, factory):
    """Triangulación: sin dueño, un docente NO puede adoptarlo. Solo rol institucional."""
    cualquiera = await _crear_docente(factory, f"DOC-E-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=None)

    async with _client(app, ["tutor"], subject=cualquiera) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/moodle-target",
            json={"moodle_courseid": 1, "moodle_cmid": 2},
        )

    assert resp.status_code == 403, resp.text


# ── GET /{examen_id}/moodle-target (c-79) ───────────────────────────────────
# Mismo gap que el POST tenía antes de C-73: la LECTURA no validaba pertenencia
# — un docente ajeno podía leer a qué curso/actividad de Moodle apunta el
# examen de una comisión que no es suya, solo conociendo el id.


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_leer_destino_moodle(app, factory):
    """RED: antes del fix devolvía 200 sin chequear pertenencia."""
    dueno = await _crear_docente(factory, f"DOC-F-{uuid.uuid4().hex[:4]}")
    ajeno = await _crear_docente(factory, f"DOC-G-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=ajeno) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/moodle-target")

    assert resp.status_code == 403, (
        "Un docente de OTRA comisión pudo leer el destino Moodle del examen ajeno. "
        f"Respuesta: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_leer_destino_moodle(app, factory):
    """Triangulación: el docente de la comisión del examen SÍ puede leerlo."""
    dueno = await _crear_docente(factory, f"DOC-H-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=dueno) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/moodle-target")

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_admin_no_esta_limitado_por_pertenencia_al_leer(app, factory):
    """Triangulación: los roles de alcance institucional leen cualquier examen."""
    dueno = await _crear_docente(factory, f"DOC-I-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen_de_comision(factory, docente_id=dueno)

    async with _client(app, ["admin_sistema"], subject="otro-sujeto") as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/moodle-target")

    assert resp.status_code == 200, resp.text
