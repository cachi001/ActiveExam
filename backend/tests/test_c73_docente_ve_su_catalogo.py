"""C-73: el DOCENTE debe ver SU catálogo (materias/comisiones/exámenes a cargo).

Bug real encontrado en verificación E2E de C-73 (Moodle Component Writeback):
``_ROLES_STAFF`` (app/presentation/api/v1/exam_content/_shared.py) NO incluye
"docente" — así que los 3 endpoints de listado (GET /exam-content,
GET /exam-content/materias, GET /exam-content/materias/{id}/comisiones) tratan
al docente como si fuera un ALUMNO (gate de inscripción C-71): lo filtran por
``comision_ids_inscriptas``, que para un docente siempre es [] (un docente no
se inscribe a su propia comisión como alumno). Resultado: un docente que entra
a "Exámenes" en el panel ve SIEMPRE "(0)" — no puede navegar a los resultados
de SU PROPIO examen aunque el endpoint de detalle (GET /{examen_id}/resultados)
sí funcione bien si se conoce la URL exacta.

`Rol.DOCENTE` está documentado en roles.py como rol de "gestión académica de lo
suyo" (ROLES_ADMIN_EXAMEN lo incluye) — el catálogo debe reflejar eso: ni "todo"
(privilegio de staff/admin) ni "sus inscripciones" (alumno), sino "lo que dicta"
(comision.docente_id == principal.subject).

DB real (DATABASE_URL, proctoring_test). Sin mocks de DB.
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
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "inscripcion",
    "opcion_respuesta",
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
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
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
        for t in _TABLES:
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
        create_exam_taking_router(session_factory=factory),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_docente(factory, legajo: str) -> str:
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=legajo,
            email=f"{legajo.lower()}@uni.edu",
            nombre="Docente",
            apellido=legajo,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_materia_comision_examen(factory, docente_id: str | None):
    """Materia + comisión (con el docente dado) + examen. Devuelve (materia_id, comision_id, examen_id)."""
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
            docente_id=docente_id,
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        ids = (materia.id, comision.id, examen.id)
        await s.commit()
    return ids


def _client(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


# ---------------------------------------------------------------------------
# RED: GET /exam-content (catálogo de examenes) — hoy vacío para el docente.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ve_su_examen_en_el_catalogo(app, factory):
    docente = await _crear_docente(factory, f"DOC-{uuid.uuid4().hex[:6]}")
    _, _, examen_id = await _crear_materia_comision_examen(factory, docente_id=docente)

    async with _client(app, ["docente"], subject=docente) as c:
        resp = await c.get("/api/v1/exam-content/")

    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    ids = [i["id"] for i in items]
    assert examen_id in ids, (
        "El docente NO ve el examen de SU PROPIA comisión en el catálogo "
        f"(items devueltos: {items})"
    )


@pytest.mark.asyncio
async def test_docente_no_ve_examen_de_comision_ajena(app, factory):
    """Triangulación: el docente NO ve el examen de una comisión que NO dicta."""
    dueno = await _crear_docente(factory, f"DOC-A-{uuid.uuid4().hex[:4]}")
    ajeno = await _crear_docente(factory, f"DOC-B-{uuid.uuid4().hex[:4]}")
    _, _, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["docente"], subject=ajeno) as c:
        resp = await c.get("/api/v1/exam-content/")

    assert resp.status_code == 200, resp.text
    ids = [i["id"] for i in resp.json()["items"]]
    assert examen_id not in ids


# ---------------------------------------------------------------------------
# RED: GET /exam-content/materias — hoy vacío para el docente.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ve_su_materia_en_el_listado(app, factory):
    docente = await _crear_docente(factory, f"DOC-{uuid.uuid4().hex[:6]}")
    materia_id, _, _ = await _crear_materia_comision_examen(factory, docente_id=docente)

    async with _client(app, ["docente"], subject=docente) as c:
        resp = await c.get("/api/v1/exam-content/materias")

    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()]
    assert materia_id in ids, (
        f"El docente NO ve su propia materia en /materias (respuesta: {resp.json()})"
    )


# ---------------------------------------------------------------------------
# RED: GET /exam-content/materias/{id}/comisiones — hoy vacío para el docente.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ve_su_comision_en_el_listado_de_materia(app, factory):
    docente = await _crear_docente(factory, f"DOC-{uuid.uuid4().hex[:6]}")
    materia_id, comision_id, _ = await _crear_materia_comision_examen(
        factory, docente_id=docente
    )

    async with _client(app, ["docente"], subject=docente) as c:
        resp = await c.get(f"/api/v1/exam-content/materias/{materia_id}/comisiones")

    assert resp.status_code == 200, resp.text
    ids = [co["id"] for co in resp.json()]
    assert comision_id in ids, (
        f"El docente NO ve su propia comisión en /materias/{{id}}/comisiones "
        f"(respuesta: {resp.json()})"
    )
