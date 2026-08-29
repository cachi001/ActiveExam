"""Dar de baja una materia tiene que darla de baja también para el alumno.

## El defecto

Verificado el 29/8/2026 contra el entorno de desarrollo: al dar de baja una
materia, el alumno seguía viéndola en «Mis materias» y seguía viendo sus
exámenes en «Mis exámenes». Lo único que cambiaba era el final del camino: al
intentar abrir el examen recibía un 409 `materia_inactiva`.

O sea, una baja que no daba de baja nada. El alumno veía un examen que no iba a
poder abrir, y cuando lo intentaba recibía un error sin haber tenido forma de
anticiparlo.

## La regla

Para el ALUMNO, una materia dada de baja y sus exámenes no existen. Para el
STAFF sigue todo visible (sesiones, notas, evidencia y auditoría), que es lo que
convierte a la baja en reversible y auditable.

## Por qué se decide por ROL y no por un parámetro

Un parámetro lo puede omitir el cliente; el rol viene del token. La regla ya
vivía server-side (el 409), solo se aplicaba demasiado tarde: esto la adelanta
al listado. El 409 se conserva como última red.

## Lo que NO se oculta

«Mis notas». La nota es del alumno y es su historia: si la materia se retira, la
nota tiene que seguir estando. Ocultarla sería quitarle algo suyo.
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
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.exam_content.taking_router import (
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "inscripcion",
    "opcion_respuesta",
    "pregunta_examen",
    "proctoring_session",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
    "usuario",
]
_TABLES_TO_CREATE = [
    UsuarioModel.__table__,
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    InscripcionModel.__table__,
]

ALUMNO = "alumno-baja-materia"


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
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
async def factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def cliente(factory):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.state.session_factory = factory
    app.include_router(
        create_exam_taking_router(session_factory=factory),
        prefix="/api/v1/exam-content",
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _escenario(factory, *, activa: bool) -> tuple[str, str]:
    """Materia (activa o no) + comisión + examen + alumno inscripto."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(
            codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}", activa=activa
        )
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
        examen = ExamenContenidoModel(
            titulo=f"Parcial {sufijo}", comision_id=comision.id, borrador=False
        )
        s.add(examen)
        alumno = UsuarioModel(
            username=ALUMNO,
            email=f"{ALUMNO}@test.local",
            password_hash="x",
            roles=["estudiante"],
        )
        s.add(alumno)
        await s.flush()
        s.add(InscripcionModel(usuario_id=alumno.id, comision_id=comision.id))
        ids = (materia.id, examen.id)
        await s.commit()
    return ids


async def _limpiar(factory) -> None:
    async with factory() as s:
        for tabla in ("inscripcion", "examen_contenido", "comision", "materia", "usuario"):
            await s.execute(text(f'TRUNCATE TABLE "{tabla}" CASCADE'))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_entre_tests(factory):
    await _limpiar(factory)
    yield


def _headers_alumno():
    return auth_headers(["estudiante"], username=ALUMNO, subject=ALUMNO)


def _headers_admin():
    return auth_headers(["admin_sistema"], username="admin", subject="admin")


# ---------------------------------------------------------------------------
# Catálogo de exámenes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_alumno_no_ve_examenes_de_una_materia_dada_de_baja(cliente, factory):
    await _escenario(factory, activa=False)
    r = await cliente.get("/api/v1/exam-content", headers=_headers_alumno())
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_con_la_materia_activa_si_los_ve(cliente, factory):
    """Triangulación: la exclusión es por la baja, no por el gate de inscripción."""
    await _escenario(factory, activa=True)
    r = await cliente.get("/api/v1/exam-content", headers=_headers_alumno())
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 1, r.text


@pytest.mark.asyncio
async def test_el_staff_sigue_viendo_los_examenes_de_la_materia_de_baja(cliente, factory):
    """La baja saca la materia de circulación, no esconde la evidencia."""
    await _escenario(factory, activa=False)
    r = await cliente.get("/api/v1/exam-content", headers=_headers_admin())
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_el_alumno_no_lo_esquiva_pidiendo_estado_todos(cliente, factory):
    """La regla vive server-side y no depende de lo que mande el cliente."""
    await _escenario(factory, activa=False)
    r = await cliente.get(
        "/api/v1/exam-content?estado=todos", headers=_headers_alumno()
    )
    assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# Mis materias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_alumno_no_ve_la_materia_dada_de_baja(cliente, factory):
    await _escenario(factory, activa=False)
    r = await cliente.get("/api/v1/exam-content/materias", headers=_headers_alumno())
    assert r.status_code == 200
    cuerpo = r.json()
    items = cuerpo["items"] if isinstance(cuerpo, dict) else cuerpo
    assert items == []


@pytest.mark.asyncio
async def test_el_staff_sigue_viendo_la_materia_dada_de_baja(cliente, factory):
    """El admin la necesita para poder reactivarla y para los filtros."""
    await _escenario(factory, activa=False)
    r = await cliente.get("/api/v1/exam-content/materias", headers=_headers_admin())
    cuerpo = r.json()
    items = cuerpo["items"] if isinstance(cuerpo, dict) else cuerpo
    assert len(items) == 1
    assert items[0]["activa"] is False
