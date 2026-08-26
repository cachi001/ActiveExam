"""Fix urgente (fuera de cualquier change formal, dominio CRÍTICO/Auth): los
endpoints de LECTURA del panel académico no exigían pertenencia por comisión,
mientras que TODAS las escrituras equivalentes sí (`_exigir_pertenencia`,
`_exigir_pertenencia_comision`). Un tutor podía LEER (nunca escribir) la
configuración, el pool de preguntas, los resultados y el listado de alumnos
de un examen/comisión que no dicta.

Encontrado en la auditoría de coherencia de datos (c-78-auditoria-coherencia-datos),
pero corregido acá directo porque es RBAC sobre datos de alumnos — no se puede
dejar en un change de auditoría de "números en pantalla".

4 endpoints, mismo bug, mismo fix (agregar el guard ya existente que sus
hermanos de escritura ya usan):
  - GET /{examen_id}/config       -> _exigir_pertenencia
  - GET /{examen_id}/preguntas    -> _exigir_pertenencia
  - GET /{examen_id}/resultados   -> _exigir_pertenencia
  - GET /comisiones/{id}/alumnos  -> _exigir_pertenencia_comision

admin_sistema SIEMPRE pasa (_ROLES_SIN_LIMITE_DE_PERTENENCIA, alcance
institucional) — se triangula acá también. El coordinador ya NO: c-79 lo sacó de
ese conjunto y lo acotó a las materias que tiene asignadas en
``materia_coordinador``, así que se triangula en las dos direcciones (ajeno → 403,
asignado → 200).

DB real (DATABASE_URL). Sin mocks de DB. Mismo patrón que
test_c74_pertenencia_comision_banco.py.
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
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
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


async def _crear_docente(factory, legajo: str) -> str:
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


async def _crear_materia_comision_examen(factory, docente_id: str | None):
    """Materia + comisión (con el docente dado) + examen.

    Devuelve (comision_id, examen_id). ``materia_id`` sale por
    ``_materia_de_comision`` cuando el test necesita asignar un coordinador."""
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
        if docente_id is not None:
            s.add(
                ComisionTutorModel(comision_id=comision.id, tutor_id=docente_id)
            )
            await s.flush()
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        ids = (comision.id, examen.id)
        await s.commit()
    return ids


def _client(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


# ---------------------------------------------------------------------------
# GET /{examen_id}/config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_leer_config_de_examen_que_no_dicta(app, factory):
    dueno = await _crear_docente(factory, f"DOC-A-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-B-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")

    assert resp.status_code == 403, (
        "Un docente pudo LEER la configuración de un examen ajeno. "
        f"Respuesta: {resp.status_code} {resp.text}"
    )
    assert resp.json()["detail"]["error"] == "examen_ajeno"


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_leer_config_de_su_examen(app, factory):
    dueno = await _crear_docente(factory, f"DOC-C-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=dueno) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_admin_sistema_puede_leer_config_de_cualquier_examen(app, factory):
    dueno = await _crear_docente(factory, f"DOC-D-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["admin_sistema"], subject="staff-1") as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")

    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# GET /{examen_id}/preguntas (pool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_leer_pool_de_examen_que_no_dicta(app, factory):
    dueno = await _crear_docente(factory, f"DOC-E-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-F-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")

    assert resp.status_code == 403, (
        "Un docente pudo LEER el pool de preguntas de un examen ajeno. "
        f"Respuesta: {resp.status_code} {resp.text}"
    )
    assert resp.json()["detail"]["error"] == "examen_ajeno"


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_leer_pool_de_su_examen(app, factory):
    dueno = await _crear_docente(factory, f"DOC-G-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=dueno) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")

    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# GET /{examen_id}/resultados
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_leer_resultados_de_examen_que_no_dicta(app, factory):
    dueno = await _crear_docente(factory, f"DOC-H-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-I-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")

    assert resp.status_code == 403, (
        "Un docente pudo LEER los resultados (notas de alumnos) de un examen "
        f"ajeno. Respuesta: {resp.status_code} {resp.text}"
    )
    assert resp.json()["detail"]["error"] == "examen_ajeno"


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_leer_resultados_de_su_examen(app, factory):
    dueno = await _crear_docente(factory, f"DOC-J-{uuid.uuid4().hex[:4]}")
    _comision_id, examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=dueno) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")

    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# GET /comisiones/{comision_id}/alumnos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_ajeno_no_puede_leer_alumnos_de_comision_que_no_dicta(app, factory):
    dueno = await _crear_docente(factory, f"DOC-K-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-L-{uuid.uuid4().hex[:4]}")
    comision_id, _examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/alumnos")

    assert resp.status_code == 403, (
        "Un docente pudo LEER el listado de alumnos de una comisión ajena. "
        f"Respuesta: {resp.status_code} {resp.text}"
    )
    assert resp.json()["detail"]["error"] == "comision_ajena"


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_leer_alumnos_de_su_comision(app, factory):
    dueno = await _crear_docente(factory, f"DOC-M-{uuid.uuid4().hex[:4]}")
    comision_id, _examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["tutor"], subject=dueno) as c:
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/alumnos")

    assert resp.status_code == 200, resp.text


async def _materia_de_comision(factory, comision_id: str) -> str:
    async with factory() as s:
        return (
            await s.execute(
                text("SELECT materia_id FROM comision WHERE id = :i"),
                {"i": comision_id},
            )
        ).scalar_one()


async def _asignar_coordinador(factory, materia_id: str, coordinador_id: str) -> None:
    async with factory() as s:
        s.add(
            MateriaCoordinadorModel(materia_id=materia_id, coordinador_id=coordinador_id)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_coordinador_ajeno_no_puede_leer_alumnos_de_una_comision(app, factory):
    """c-79: antes pasaba SIEMPRE (alcance institucional, igual que un admin).
    Ahora un coordinador sin esa materia asignada es tan ajeno como un tutor."""
    dueno = await _crear_docente(factory, f"DOC-N-{uuid.uuid4().hex[:4]}")
    ajeno = await _crear_docente(factory, f"COORD-X-{uuid.uuid4().hex[:4]}")
    comision_id, _examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["coordinador"], subject=ajeno) as c:
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/alumnos")

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_coordinador_de_la_materia_si_puede_leer_alumnos(app, factory):
    """Triangulación: la asignación en materia_coordinador es lo que lo habilita."""
    dueno = await _crear_docente(factory, f"DOC-N-{uuid.uuid4().hex[:4]}")
    coord = await _crear_docente(factory, f"COORD-Y-{uuid.uuid4().hex[:4]}")
    comision_id, _examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)
    await _asignar_coordinador(
        factory, await _materia_de_comision(factory, comision_id), coord
    )

    async with _client(app, ["coordinador"], subject=coord) as c:
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/alumnos")

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_subject_no_uuid_da_403_y_no_revienta(app, factory):
    """Un `sub` que no es UUID (identidad federada con formato propio, token
    malformado) chocaba contra la columna UUID y salía por un 500 de asyncpg —
    donde correspondía un 403 limpio. Denegar nunca es reventar."""
    dueno = await _crear_docente(factory, f"DOC-N-{uuid.uuid4().hex[:4]}")
    comision_id, _examen_id = await _crear_materia_comision_examen(factory, docente_id=dueno)

    async with _client(app, ["coordinador"], subject="staff-2") as c:
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/alumnos")

    assert resp.status_code == 403, resp.text
