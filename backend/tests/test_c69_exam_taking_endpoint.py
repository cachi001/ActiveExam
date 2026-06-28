"""3.3 RED -> 3.4 GREEN -> 3.5 TRIANGULATE: tests del endpoint de lectura para rendir.

Tests de integración (requieren DATABASE_URL).
Los tests de 401 (sin auth) no requieren DB.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_NEW_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido")

# ---------------------------------------------------------------------------
# Fixtures: app sin DB para tests de 401
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_noauth():
    """App mínima con el taking router pero sin DB — para tests 401."""
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_taking_router(session_factory=None)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_noauth(app_noauth):
    async with AsyncClient(
        transport=ASGITransport(app=app_noauth), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures: app con DB real
# ---------------------------------------------------------------------------


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
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_student(db_engine):
    """App con taking router + DB real + JWT de test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_taking_router(session_factory=factory)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app, factory


@pytest_asyncio.fixture
async def client_student(app_student):
    app, _ = app_student
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def examen_guardado(app_student):
    """Crea y persiste un examen de contenido con 2 preguntas."""
    _, factory = app_student
    examen = ExamenContenido(
        titulo="Parcial de Prueba",
        preguntas=(
            Pregunta(
                id=None,
                enunciado="¿Capital de Francia?",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(id=None, texto="París", es_correcta=True, orden=0),
                    OpcionRespuesta(id=None, texto="Madrid", es_correcta=False, orden=1),
                    OpcionRespuesta(id=None, texto="Roma", es_correcta=False, orden=2),
                ),
            ),
            Pregunta(
                id=None,
                enunciado="El Sol es una estrella.",
                tipo="truefalse",
                orden=1,
                opciones=(
                    OpcionRespuesta(id=None, texto="Verdadero", es_correcta=True, orden=0),
                    OpcionRespuesta(id=None, texto="Falso", es_correcta=False, orden=1),
                ),
            ),
        ),
        comision_id=None,
    )
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        guardado = await repo.guardar(examen)
        await session.commit()
    return guardado


# ---------------------------------------------------------------------------
# 3.3 RED: tests de auth y 404 (sin DB para 401)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_sin_token_401(client_noauth):
    """Sin Authorization header -> 401."""
    resp = await client_noauth.get("/api/v1/exam-content/00000000-0000-0000-0000-000000000001")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 3.3 RED / 3.4 GREEN: tests funcionales (requieren DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_examen_existente_200(client_student, examen_guardado):
    """Alumno autenticado obtiene el examen con preguntas y opciones (sin es_correcta)."""
    resp = await client_student.get(f"/api/v1/exam-content/{examen_guardado.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == examen_guardado.id
    assert data["titulo"] == "Parcial de Prueba"
    assert len(data["preguntas"]) == 2


@pytest.mark.asyncio
async def test_respuesta_no_incluye_es_correcta(client_student, examen_guardado):
    """D3: la respuesta NO incluye es_correcta en ninguna opción."""
    resp = await client_student.get(f"/api/v1/exam-content/{examen_guardado.id}")
    assert resp.status_code == 200
    data = resp.json()
    for pregunta in data["preguntas"]:
        for opcion in pregunta["opciones"]:
            assert "es_correcta" not in opcion, (
                f"La opción {opcion} NO debe exponer es_correcta al cliente."
            )


@pytest.mark.asyncio
async def test_examen_inexistente_404(client_student):
    """Examen inexistente -> 404 sin filtrar datos de otros exámenes."""
    resp = await client_student.get(
        "/api/v1/exam-content/00000000-0000-0000-0000-000000000099"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3.5 TRIANGULATE: orden determinístico y aislamiento
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orden_determinístico_dos_requests(client_student, examen_guardado):
    """Dos requests al mismo examen devuelven el mismo orden de preguntas y opciones."""
    r1 = await client_student.get(f"/api/v1/exam-content/{examen_guardado.id}")
    r2 = await client_student.get(f"/api/v1/exam-content/{examen_guardado.id}")
    assert r1.status_code == 200
    assert r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    ids_preguntas_1 = [p["id"] for p in d1["preguntas"]]
    ids_preguntas_2 = [p["id"] for p in d2["preguntas"]]
    assert ids_preguntas_1 == ids_preguntas_2, "El orden de preguntas debe ser determinístico."
    for p1, p2 in zip(d1["preguntas"], d2["preguntas"]):
        ids_opciones_1 = [o["id"] for o in p1["opciones"]]
        ids_opciones_2 = [o["id"] for o in p2["opciones"]]
        assert ids_opciones_1 == ids_opciones_2, "El orden de opciones debe ser determinístico."


@pytest.mark.asyncio
async def test_examen_inexistente_no_filtra_datos_de_otro_examen(
    client_student, examen_guardado
):
    """Un id inexistente devuelve 404 sin exponer datos del examen que sí existe."""
    resp = await client_student.get(
        "/api/v1/exam-content/00000000-0000-0000-0000-000000000099"
    )
    assert resp.status_code == 404
    # La respuesta de 404 no debe contener datos del examen guardado
    body = resp.text
    assert examen_guardado.titulo not in body
