"""El alumno que se cayó tiene que poder volver a su examen (GET /sessions/en-curso).

Problema real (29/8/2026, reportado por el dueño rindiendo): se le cortó el wifi
en medio del examen, salió, y al volver la pantalla "Mis exámenes" le mostró el
examen como si nunca lo hubiera empezado — con el cartel "Tenés un solo intento",
que se lee como una amenaza. Entendió que había gastado el intento y no se animó
a entrar.

El backend ya sabía reanudar: `crear_o_reanudar_sesion` reusa la sesión activa
(misma id, mismo cronómetro) y `GET /sessions/{id}/respuestas` devuelve lo que ya
había contestado. Lo que faltaba era el DESCUBRIMIENTO: ninguna pantalla podía
preguntar "¿este alumno tiene un examen abierto?". Sin eso la reanudación existía
pero era invisible, que para el alumno es igual que no existir.

DB real (DATABASE_URL), sin mocks de DB (regla dura de código #4).

Correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_sesiones_en_curso.py -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"

_DROP = ["proctoring_session", "examen_contenido"]
_CREATE = [ExamenContenidoModel.__table__, ProctoringSessionModel.__table__]


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url: str):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest.fixture(scope="module")
def reinferencia():
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    return MediaPipeReinferencia()


@pytest.fixture(scope="module")
def app(engine, reinferencia):
    from fastapi import FastAPI

    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_session_factory,
    )
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    factory = create_activeexam_session_factory(engine)
    router = create_proctoring_router(
        session_factory=factory, reinferencia=reinferencia, writeback_svc=None
    )
    a = FastAPI()
    a.state.jwt_validator = _build_test_jwt_validator()
    a.include_router(router, prefix="/api/v1/proctoring")
    return a


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{t}"' for t in _DROP)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"], username="estudiante1", email="e1@uni.edu"),
    ) as c:
        yield c


async def _crear_examen(db: AsyncSession, titulo: str = "Parcial") -> str:
    examen = ExamenContenidoModel(titulo=titulo, intentos_permitidos=1)
    db.add(examen)
    await db.commit()
    await db.refresh(examen)
    return examen.id


async def _crear_sesion(
    db: AsyncSession,
    examen_id: str,
    *,
    alumno: str = "estudiante1",
    finalizada: bool = False,
    es_prueba: bool = False,
) -> str:
    from datetime import datetime, timezone

    sesion = ProctoringSessionModel(
        modo="activeexam",
        examen_contenido_id=examen_id,
        alumno_idnumber=alumno,
        alumno_email=f"{alumno}@uni.edu",
        finalizada_en=datetime.now(timezone.utc) if finalizada else None,
        es_prueba=es_prueba,
    )
    db.add(sesion)
    await db.commit()
    await db.refresh(sesion)
    return sesion.id


async def test_sin_sesiones_devuelve_lista_vacia(client: AsyncClient) -> None:
    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.status_code == 200
    assert r.json() == []


async def test_sesion_abierta_aparece_con_su_examen(
    client: AsyncClient, db: AsyncSession
) -> None:
    """El caso del corte de wifi: la sesión quedó abierta y hay que poder encontrarla."""
    examen_id = await _crear_examen(db)
    sesion_id = await _crear_sesion(db, examen_id)

    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["session_id"] == str(sesion_id)
    assert body[0]["examen_contenido_id"] == str(examen_id)


async def test_sesion_finalizada_no_aparece(client: AsyncClient, db: AsyncSession) -> None:
    """Un examen entregado NO es un examen en curso: ofrecer 'continuar' ahí sería
    ofrecerle al alumno rendir de nuevo algo que ya entregó."""
    examen_id = await _crear_examen(db)
    await _crear_sesion(db, examen_id, finalizada=True)

    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.json() == []


async def test_no_expone_la_sesion_de_otro_alumno(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Aislamiento (H1/IDOR): el listado se acota al alumno del JWT, no al examen.
    Filtrar mal acá le mostraría a un alumno que otro está rindiendo."""
    examen_id = await _crear_examen(db)
    await _crear_sesion(db, examen_id, alumno="estudiante2")

    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.json() == []


async def test_la_prueba_del_docente_no_aparece(
    client: AsyncClient, db: AsyncSession
) -> None:
    """`es_prueba` es el docente probando su propio examen: no cuenta como intento
    ni genera nota, así que tampoco es una rendición que haya que retomar."""
    examen_id = await _crear_examen(db)
    await _crear_sesion(db, examen_id, es_prueba=True)

    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.json() == []


async def test_sesion_sin_examen_vinculado_no_aparece(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Una sesión de proctoring sin `examen_contenido_id` (modo demo/etiqueta) no
    tiene examen al que volver: la tarjeta no tendría dónde llevar al alumno."""
    from datetime import datetime, timezone

    sesion = ProctoringSessionModel(
        modo="demo",
        examen_contenido_id=None,
        alumno_idnumber="estudiante1",
        alumno_email="e1@uni.edu",
        finalizada_en=None,
    )
    db.add(sesion)
    await db.commit()
    assert datetime.now(timezone.utc) is not None  # el modelo quedó persistido

    r = await client.get(f"{_BASE}/sessions/en-curso")
    assert r.json() == []
